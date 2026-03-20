"""Observability / Traces API."""
from __future__ import annotations

from typing import Annotated, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.models.trace import AgentTrace, TraceSpan

router = APIRouter(prefix="/api/traces", tags=["observability"])


@router.get("")
async def list_traces(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    agent_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    terminal_state: Optional[str] = Query(None),
    min_cost_usd: Optional[float] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """OBS-03: Query traces by multiple dimensions."""
    q = select(AgentTrace).order_by(AgentTrace.started_at.desc())
    if agent_id:
        q = q.where(AgentTrace.agent_id == agent_id)
    if org_id:
        q = q.where(AgentTrace.org_id == org_id)
    if terminal_state:
        q = q.where(AgentTrace.terminal_state == terminal_state)
    if min_cost_usd is not None:
        q = q.where(AgentTrace.total_cost_usd >= min_cost_usd)
    if since:
        q = q.where(AgentTrace.started_at >= since)
    if until:
        q = q.where(AgentTrace.started_at <= until)
    q = q.limit(limit).offset(offset)

    result = await db.execute(q)
    traces = result.scalars().all()

    return [
        {
            "trace_id": t.trace_id,
            "agent_id": t.agent_id,
            "org_id": t.org_id,
            "team_id": t.team_id,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "ended_at": t.ended_at.isoformat() if t.ended_at else None,
            "duration_ms": t.duration_ms,
            "terminal_state": t.terminal_state,
            "total_input_tokens": t.total_input_tokens,
            "total_output_tokens": t.total_output_tokens,
            "total_cost_usd": round(t.total_cost_usd, 6),
            "framework": t.framework,
            "environment": t.environment,
            "parent_trace_id": t.parent_trace_id,
        }
        for t in traces
    ]


@router.get("/{trace_id}")
async def get_trace(
    trace_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """OBS-01: Get full trace with all spans."""
    result = await db.execute(select(AgentTrace).where(AgentTrace.trace_id == trace_id))
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

    spans_result = await db.execute(
        select(TraceSpan)
        .where(TraceSpan.trace_id == trace_id)
        .order_by(TraceSpan.started_at)
    )
    spans = spans_result.scalars().all()

    return {
        "trace_id": trace.trace_id,
        "agent_id": trace.agent_id,
        "org_id": trace.org_id,
        "team_id": trace.team_id,
        "parent_trace_id": trace.parent_trace_id,
        "parent_span_id": trace.parent_span_id,
        "started_at": trace.started_at.isoformat() if trace.started_at else None,
        "ended_at": trace.ended_at.isoformat() if trace.ended_at else None,
        "duration_ms": trace.duration_ms,
        "terminal_state": trace.terminal_state,
        "total_input_tokens": trace.total_input_tokens,
        "total_output_tokens": trace.total_output_tokens,
        "total_cost_usd": round(trace.total_cost_usd, 6),
        "framework": trace.framework,
        "environment": trace.environment,
        "spans": [
            {
                "span_id": s.span_id,
                "span_type": s.span_type,
                "name": s.name,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "duration_ms": s.duration_ms,
                "model_id": s.model_id,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
                "cost_usd": s.cost_usd,
                "inputs": s.inputs,
                "outputs": s.outputs,
                "inputs_redacted": s.inputs_redacted,
                "policy_decision": s.policy_decision,
                "policy_id": s.policy_id,
                "status": s.status,
                "error": s.error,
            }
            for s in spans
        ],
    }
