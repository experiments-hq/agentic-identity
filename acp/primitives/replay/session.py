"""Incident Replay — step-through reconstruction of agent runs (RPL-01…RPL-05)."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.config import settings
from acp.models.audit import ReplaySession
from acp.models.trace import AgentTrace, TraceSpan


# ── Session creation ──────────────────────────────────────────────────────────

async def create_replay_session(
    db: AsyncSession,
    *,
    trace_id: str,
    created_by: str,
    counterfactual: bool = False,
    counterfactual_from_step: Optional[int] = None,
    counterfactual_overrides: Optional[dict] = None,
) -> ReplaySession:
    """Create a replay session for a trace_id (RPL-01)."""
    # Verify trace exists
    result = await db.execute(
        select(AgentTrace).where(AgentTrace.trace_id == trace_id)
    )
    trace = result.scalar_one_or_none()
    if not trace:
        raise ValueError(f"Trace {trace_id} not found")

    # Build ordered step index from spans
    spans_result = await db.execute(
        select(TraceSpan.span_id)
        .where(TraceSpan.trace_id == trace_id)
        .order_by(TraceSpan.started_at)
    )
    step_index = [row[0] for row in spans_result.all()]

    session = ReplaySession(
        session_id=str(uuid.uuid4()),
        trace_id=trace_id,
        created_by=created_by,
        current_step=0,
        is_counterfactual=counterfactual,
        counterfactual_from_step=counterfactual_from_step,
        counterfactual_overrides=counterfactual_overrides,
        step_index=step_index,
    )
    db.add(session)
    await db.flush()
    return session


async def generate_share_link(
    db: AsyncSession,
    session_id: str,
    expiry_days: Optional[int] = None,
) -> str:
    """Generate a time-limited share token (RPL-05). Returns the token."""
    result = await db.execute(
        select(ReplaySession).where(ReplaySession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError(f"Replay session {session_id} not found")

    token = secrets.token_urlsafe(32)
    days = expiry_days or settings.replay_link_expiry_days
    session.share_token = token
    session.share_expires_at = datetime.now(tz=timezone.utc) + timedelta(days=days)
    await db.flush()
    return token


# ── Navigation ────────────────────────────────────────────────────────────────

async def get_step(
    db: AsyncSession,
    session_id: str,
    step: int,
) -> dict:
    """Return full data for step N (RPL-02, RPL-03)."""
    result = await db.execute(
        select(ReplaySession).where(ReplaySession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError(f"Replay session {session_id} not found")

    index = session.step_index
    if step < 0 or step >= len(index):
        raise ValueError(f"Step {step} out of range (0..{len(index)-1})")

    span_id = index[step]
    span_result = await db.execute(
        select(TraceSpan).where(TraceSpan.span_id == span_id)
    )
    span = span_result.scalar_one_or_none()
    if not span:
        raise ValueError(f"Span {span_id} not found")

    # Apply counterfactual override if present
    inputs = span.inputs
    if session.is_counterfactual and session.counterfactual_overrides:
        override = session.counterfactual_overrides.get(str(step))
        if override:
            inputs = override

    return {
        "step": step,
        "total_steps": len(index),
        "span_id": span.span_id,
        "span_type": span.span_type,
        "name": span.name,
        "started_at": span.started_at.isoformat() if span.started_at else None,
        "ended_at": span.ended_at.isoformat() if span.ended_at else None,
        "duration_ms": span.duration_ms,
        "model_id": span.model_id,
        "input_tokens": span.input_tokens,
        "output_tokens": span.output_tokens,
        "cost_usd": span.cost_usd,
        "inputs": inputs,
        "outputs": span.outputs,
        "inputs_redacted": span.inputs_redacted,
        "policy_decision": span.policy_decision,
        "policy_id": span.policy_id,
        "status": span.status,
        "error": span.error,
        "is_counterfactual_override": (
            session.is_counterfactual
            and session.counterfactual_overrides is not None
            and str(step) in session.counterfactual_overrides
        ),
    }


async def navigate(
    db: AsyncSession,
    session_id: str,
    *,
    direction: Optional[str] = None,
    jump_to: Optional[int] = None,
    jump_to_first_violation: bool = False,
    jump_to_terminal: bool = False,
) -> dict:
    """Move the current_step pointer and return the new step data (RPL-02)."""
    result = await db.execute(
        select(ReplaySession).where(ReplaySession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError(f"Replay session {session_id} not found")

    index = session.step_index
    current = session.current_step

    if jump_to is not None:
        current = jump_to
    elif direction == "forward":
        current = min(current + 1, len(index) - 1)
    elif direction == "backward":
        current = max(current - 1, 0)
    elif jump_to_first_violation:
        current = await _find_first_violation(db, index)
    elif jump_to_terminal:
        current = len(index) - 1

    session.current_step = current
    await db.flush()
    return await get_step(db, session_id, current)


async def _find_first_violation(db: AsyncSession, index: list[str]) -> int:
    for i, span_id in enumerate(index):
        result = await db.execute(
            select(TraceSpan.policy_decision).where(TraceSpan.span_id == span_id)
        )
        decision = result.scalar_one_or_none()
        if decision in ("deny", "require_approval"):
            return i
    return len(index) - 1  # no violation found — jump to end
