"""Budget Controls API."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.models.budget import BudgetLimit, BudgetUsage
from acp.primitives.audit.logger import EventType, log_event
from acp.primitives.budget.tracker import _get_or_create_usage, _window_bounds

router = APIRouter(prefix="/api/budgets", tags=["budget"])


class CreateBudgetRequest(BaseModel):
    org_id: str
    scope_level: str  # org | team | agent
    scope_id: str
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    window: str  # rolling_24h | rolling_7d | rolling_30d | calendar_month
    alert_thresholds: list[int] = [50, 80, 95, 100]
    alert_channels: list[str] = []
    created_by: str


@router.post("", status_code=201)
async def create_budget(
    body: CreateBudgetRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """BUD-01: Create a budget limit."""
    valid_windows = {"rolling_24h", "rolling_7d", "rolling_30d", "calendar_month"}
    if body.window not in valid_windows:
        raise HTTPException(status_code=422, detail=f"window must be one of {valid_windows}")
    if body.scope_level not in ("org", "team", "agent"):
        raise HTTPException(status_code=422, detail="scope_level must be org, team, or agent")
    if not body.max_tokens and not body.max_cost_usd:
        raise HTTPException(status_code=422, detail="At least one of max_tokens or max_cost_usd required")

    budget = BudgetLimit(
        org_id=body.org_id,
        scope_level=body.scope_level,
        scope_id=body.scope_id,
        max_tokens=body.max_tokens,
        max_cost_usd=body.max_cost_usd,
        window=body.window,
        alert_thresholds=body.alert_thresholds,
        alert_channels=body.alert_channels,
        is_active=True,
        created_by=body.created_by,
    )
    db.add(budget)
    await db.flush()

    await log_event(
        db,
        event_type=EventType.BUDGET_CREATED,
        actor_type="user",
        actor_id=body.created_by,
        resource_type="budget",
        resource_id=budget.budget_id,
        action="create",
        outcome="success",
        payload={
            "org_id": body.org_id,
            "scope_level": body.scope_level,
            "scope_id": body.scope_id,
            "max_cost_usd": body.max_cost_usd,
            "window": body.window,
        },
    )

    return {
        "budget_id": budget.budget_id,
        "scope_level": body.scope_level,
        "scope_id": body.scope_id,
        "max_cost_usd": body.max_cost_usd,
        "max_tokens": body.max_tokens,
        "window": body.window,
    }


@router.get("/{budget_id}/usage")
async def get_usage(
    budget_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """BUD-02 + BUD-05: Get current usage for a budget."""
    result = await db.execute(select(BudgetLimit).where(BudgetLimit.budget_id == budget_id))
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

    usage = await _get_or_create_usage(db, budget)
    ws, we = _window_bounds(budget.window)

    pct_cost = 0.0
    if budget.max_cost_usd and budget.max_cost_usd > 0:
        pct_cost = (usage.used_cost_usd / budget.max_cost_usd) * 100

    return {
        "budget_id": budget_id,
        "scope_level": budget.scope_level,
        "scope_id": budget.scope_id,
        "window": budget.window,
        "window_start": usage.window_start.isoformat(),
        "window_end": usage.window_end.isoformat(),
        "max_tokens": budget.max_tokens,
        "max_cost_usd": budget.max_cost_usd,
        "used_tokens": usage.used_tokens,
        "used_cost_usd": round(usage.used_cost_usd, 6),
        "pct_cost_used": round(pct_cost, 1),
        "hard_stopped": usage.hard_stopped,
        "hard_stopped_at": usage.hard_stopped_at.isoformat() if usage.hard_stopped_at else None,
        "model_breakdown": usage.model_breakdown,
        "last_updated": usage.last_updated.isoformat() if usage.last_updated else None,
    }


@router.get("")
async def list_budgets(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    org_id: Optional[str] = Query(None),
    scope_level: Optional[str] = Query(None),
    scope_id: Optional[str] = Query(None),
):
    """List all budgets for an org."""
    q = select(BudgetLimit)
    if org_id:
        q = q.where(BudgetLimit.org_id == org_id)
    if scope_level:
        q = q.where(BudgetLimit.scope_level == scope_level)
    if scope_id:
        q = q.where(BudgetLimit.scope_id == scope_id)

    result = await db.execute(q)
    budgets = result.scalars().all()

    return [
        {
            "budget_id": b.budget_id,
            "org_id": b.org_id,
            "scope_level": b.scope_level,
            "scope_id": b.scope_id,
            "max_tokens": b.max_tokens,
            "max_cost_usd": b.max_cost_usd,
            "window": b.window,
            "is_active": b.is_active,
        }
        for b in budgets
    ]
