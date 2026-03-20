"""Approvals Engine API."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.models.agent import Agent
from acp.models.approval import ApprovalRequest
from acp.primitives.approvals.engine import submit_decision
from acp.primitives.audit.logger import EventType, log_event

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class DecisionRequest(BaseModel):
    action: str  # approve | deny | escalate
    actor: str
    reason: Optional[str] = None
    conditions: Optional[dict] = None


@router.get("")
async def list_approvals(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    status: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List approval requests (queue view)."""
    q = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status:
        q = q.where(ApprovalRequest.status == status)
    if agent_id:
        q = q.where(ApprovalRequest.agent_id == agent_id)
    if org_id:
        q = q.where(
            ApprovalRequest.agent_id.in_(
                select(Agent.agent_id).where(Agent.org_id == org_id)
            )
        )
    q = q.limit(limit).offset(offset)

    result = await db.execute(q)
    requests = result.scalars().all()

    return [
        {
            "request_id": r.request_id,
            "agent_id": r.agent_id,
            "policy_id": r.policy_id,
            "action_type": r.action_type,
            "action_detail": r.action_detail,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "expires_at": r.expires_at.isoformat(),
            "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            "decided_by": r.decided_by,
            "decision_reason": r.decision_reason,
        }
        for r in requests
    ]


@router.get("/{request_id}")
async def get_approval(
    request_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.request_id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail=f"Approval request {request_id} not found")

    return {
        "request_id": req.request_id,
        "agent_id": req.agent_id,
        "trace_id": req.trace_id,
        "policy_id": req.policy_id,
        "action_type": req.action_type,
        "action_detail": req.action_detail,
        "status": req.status,
        "timeout_minutes": req.timeout_minutes,
        "created_at": req.created_at.isoformat(),
        "expires_at": req.expires_at.isoformat(),
        "decided_at": req.decided_at.isoformat() if req.decided_at else None,
        "decided_by": req.decided_by,
        "decision_reason": req.decision_reason,
        "approval_conditions": req.approval_conditions,
        "notified_channels": req.notified_channels,
    }


@router.post("/{request_id}/decide")
async def decide(
    request_id: str,
    body: DecisionRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """APR-03: Submit approve / deny / escalate decision."""
    try:
        req = await submit_decision(
            db,
            request_id,
            action=body.action,
            actor=body.actor,
            reason=body.reason,
            conditions=body.conditions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    event_type_map = {
        "approve": EventType.APPROVAL_APPROVED,
        "deny": EventType.APPROVAL_DENIED,
        "escalate": EventType.APPROVAL_ESCALATED,
    }
    await log_event(
        db,
        event_type=event_type_map.get(body.action, EventType.APPROVAL_APPROVED),
        actor_type="user",
        actor_id=body.actor,
        resource_type="approval_request",
        resource_id=request_id,
        action=body.action,
        outcome=req.status,
        payload={"reason": body.reason, "conditions": body.conditions},
    )

    return {
        "request_id": req.request_id,
        "status": req.status,
        "decided_by": req.decided_by,
        "decided_at": req.decided_at.isoformat() if req.decided_at else None,
    }
