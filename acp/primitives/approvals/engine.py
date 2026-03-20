"""Approvals Engine — durable human-in-the-loop gates (APR-01…APR-05)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.config import settings
from acp.models.approval import ApprovalRequest, ApprovalDecision
from acp.primitives.approvals.notifications import send_approval_notification

log = logging.getLogger(__name__)

# Map of request_id -> asyncio.Event (agents blocked waiting for approval)
_pending_events: dict[str, asyncio.Event] = {}
_pending_lock = asyncio.Lock()


# ── Create approval request ───────────────────────────────────────────────────

async def create_approval_request(
    db: AsyncSession,
    *,
    agent_id: str,
    trace_id: Optional[str],
    policy_id: str,
    action_type: str,
    action_detail: dict,
    requesting_user: Optional[str] = None,
    approval_config: Optional[dict] = None,
    base_url: str = "",
) -> ApprovalRequest:
    """Create an ApprovalRequest and send notifications."""
    cfg = approval_config or {}
    timeout_minutes = cfg.get("timeout_minutes", settings.approval_default_timeout_minutes)
    timeout_action = cfg.get("timeout_action", settings.approval_default_timeout_action)
    escalate_to = cfg.get("escalate_to")
    channels: list[str] = []

    # Collect notification channels from policy alert config
    for ch in cfg.get("channels", []):
        channels.append(ch)

    expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=timeout_minutes)

    req = ApprovalRequest(
        request_id=str(uuid.uuid4()),
        agent_id=agent_id,
        trace_id=trace_id,
        policy_id=policy_id,
        action_type=action_type,
        action_detail=action_detail,
        requesting_user=requesting_user,
        status="pending",
        timeout_minutes=timeout_minutes,
        escalate_to=escalate_to,
        timeout_action=timeout_action,
        expires_at=expires_at,
        notified_channels=[],
    )
    db.add(req)
    await db.flush()

    # Register event for blocking wait
    event = asyncio.Event()
    async with _pending_lock:
        _pending_events[req.request_id] = event

    # Send notifications asynchronously (don't block on this)
    if channels:
        asyncio.create_task(
            _send_notifications(req, channels, base_url)
        )

    return req


async def _send_notifications(
    req: ApprovalRequest,
    channels: list[str],
    base_url: str,
) -> None:
    try:
        notified = await send_approval_notification(
            request_id=req.request_id,
            agent_id=req.agent_id,
            action_type=req.action_type,
            action_detail=req.action_detail,
            policy_id=req.policy_id,
            expires_at=req.expires_at.isoformat(),
            channels=channels,
            base_url=base_url,
        )
        req.notified_channels = notified
    except Exception as exc:
        log.error("Notification error for request %s: %s", req.request_id, exc)


# ── Wait for decision (used by proxy to block agent) ─────────────────────────

async def wait_for_decision(
    db: AsyncSession,
    request_id: str,
) -> ApprovalRequest:
    """Block until approved/denied/timed-out. Returns final ApprovalRequest state."""
    async with _pending_lock:
        event = _pending_events.get(request_id)

    if event is None:
        # Load from DB (after restart, event won't be in memory)
        result = await db.execute(
            select(ApprovalRequest).where(ApprovalRequest.request_id == request_id)
        )
        req = result.scalar_one_or_none()
        if not req or req.status != "pending":
            return req
        # Re-create event and wait with timeout
        event = asyncio.Event()
        async with _pending_lock:
            _pending_events[request_id] = event

    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.request_id == request_id)
    )
    req = result.scalar_one()
    timeout_seconds = req.timeout_minutes * 60

    try:
        await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        await _handle_timeout(db, req)
    finally:
        async with _pending_lock:
            _pending_events.pop(request_id, None)

    await db.refresh(req)
    return req


# ── Submit decision ───────────────────────────────────────────────────────────

async def submit_decision(
    db: AsyncSession,
    request_id: str,
    *,
    action: str,
    actor: str,
    reason: Optional[str] = None,
    conditions: Optional[dict] = None,
) -> ApprovalRequest:
    """Record approve / deny / escalate decision and wake the waiting agent."""
    if action not in ("approve", "deny", "escalate"):
        raise ValueError(f"Invalid action '{action}'. Must be: approve, deny, escalate")
    if action == "deny" and not reason:
        raise ValueError("A reason is required when denying an approval request")

    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.request_id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise ValueError(f"Approval request {request_id} not found")
    if req.status != "pending":
        raise ValueError(f"Request {request_id} is already {req.status}")

    # Map action to status
    status_map = {"approve": "approved", "deny": "denied", "escalate": "escalated"}
    req.status = status_map[action]
    req.decided_at = datetime.now(tz=timezone.utc)
    req.decided_by = actor
    req.decision_reason = reason
    req.approval_conditions = conditions

    decision_record = ApprovalDecision(
        request_id=request_id,
        action=action,
        actor=actor,
        reason=reason,
        conditions=conditions,
    )
    db.add(decision_record)
    await db.flush()

    # Wake the waiting coroutine
    async with _pending_lock:
        event = _pending_events.get(request_id)
    if event:
        event.set()

    return req


async def _handle_timeout(db: AsyncSession, req: ApprovalRequest) -> None:
    """Apply configured timeout action when approval window expires."""
    timeout_action = req.timeout_action
    status = {
        "deny": "timed_out",
        "approve": "approved",
        "escalate": "escalated",
    }.get(timeout_action, "timed_out")

    req.status = status
    req.decided_at = datetime.now(tz=timezone.utc)
    req.decided_by = "system:timeout"
    req.decision_reason = f"Approval timed out after {req.timeout_minutes} minutes"
    await db.flush()

    log.info(
        "Approval request %s timed out → %s", req.request_id, req.status
    )
