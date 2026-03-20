"""Observability — automatic trace/span capture (OBS-01…OBS-07)."""
from __future__ import annotations

import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from acp.config import settings
from acp.models.trace import AgentTrace, TraceSpan


# ── Cost table (USD per 1K tokens) ────────────────────────────────────────────
# These are approximate — updated periodically.
_MODEL_COST_PER_1K: dict[str, tuple[float, float]] = {
    "claude-opus-4-6":    (0.005, 0.025),
    "claude-sonnet-4-6":  (0.003, 0.015),
    "claude-haiku-4-5":   (0.001, 0.005),
    "gpt-4o":             (0.005, 0.015),
    "gpt-4o-mini":        (0.00015, 0.0006),
    "gpt-4-turbo":        (0.01, 0.03),
}


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    costs = _MODEL_COST_PER_1K.get(model_id, (0.002, 0.002))
    return (input_tokens * costs[0] + output_tokens * costs[1]) / 1000.0


# ── PII redaction ─────────────────────────────────────────────────────────────
_PII_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                                  # SSN
    re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b"),  # CC
]


def redact_pii(text: str) -> str:
    for pat in _PII_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def redact_dict(d: Any) -> Any:
    if isinstance(d, dict):
        return {k: redact_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [redact_dict(v) for v in d]
    if isinstance(d, str):
        return redact_pii(d)
    return d


# ── Trace context manager ─────────────────────────────────────────────────────

class TraceContext:
    """Holds mutable state for the current trace during a request."""

    def __init__(self, trace: AgentTrace, db: AsyncSession) -> None:
        self._trace = trace
        self._db = db
        self._spans: list[TraceSpan] = []

    @property
    def trace_id(self) -> str:
        return self._trace.trace_id

    async def add_span(
        self,
        *,
        span_type: str,
        name: str,
        started_at: datetime,
        ended_at: Optional[datetime] = None,
        model_id: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        inputs: Optional[dict] = None,
        outputs: Optional[dict] = None,
        policy_decision: Optional[str] = None,
        policy_id: Optional[str] = None,
        status: str = "ok",
        error: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ) -> TraceSpan:
        duration_ms = None
        if ended_at:
            duration_ms = (ended_at - started_at).total_seconds() * 1000

        cost_usd = None
        if model_id and input_tokens is not None and output_tokens is not None:
            cost_usd = estimate_cost(model_id, input_tokens, output_tokens)

        # Apply PII redaction if enabled
        redacted = False
        if settings.pii_redaction_enabled:
            if inputs:
                inputs = redact_dict(inputs)
                redacted = True
            if outputs:
                outputs = redact_dict(outputs)
                redacted = True

        span = TraceSpan(
            span_id=str(uuid.uuid4()),
            trace_id=self._trace.trace_id,
            parent_span_id=parent_span_id,
            span_type=span_type,
            name=name,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            inputs=inputs,
            outputs=outputs,
            inputs_redacted=redacted,
            policy_decision=policy_decision,
            policy_id=policy_id,
            status=status,
            error=error,
        )
        self._db.add(span)
        self._spans.append(span)

        # Roll up cost into trace
        if cost_usd:
            self._trace.total_cost_usd += cost_usd
        if input_tokens:
            self._trace.total_input_tokens += input_tokens
        if output_tokens:
            self._trace.total_output_tokens += output_tokens

        return span

    async def finish(self, terminal_state: str = "success") -> None:
        self._trace.ended_at = datetime.now(tz=timezone.utc)
        self._trace.terminal_state = terminal_state
        if self._trace.started_at:
            self._trace.duration_ms = (
                self._trace.ended_at - self._trace.started_at
            ).total_seconds() * 1000


@asynccontextmanager
async def start_trace(
    db: AsyncSession,
    *,
    agent_id: str,
    org_id: str,
    team_id: str,
    framework: Optional[str] = None,
    environment: Optional[str] = None,
    parent_trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> AsyncGenerator[TraceContext, None]:
    """Context manager: creates an AgentTrace row, yields TraceContext, then finalises."""
    trace = AgentTrace(
        trace_id=str(uuid.uuid4()),
        agent_id=agent_id,
        org_id=org_id,
        team_id=team_id,
        started_at=datetime.now(tz=timezone.utc),
        framework=framework,
        environment=environment,
        parent_trace_id=parent_trace_id,
        parent_span_id=parent_span_id,
    )
    db.add(trace)
    await db.flush()

    ctx = TraceContext(trace, db)
    try:
        yield ctx
        await ctx.finish("success")
    except Exception as exc:
        await ctx.finish("failure")
        raise
