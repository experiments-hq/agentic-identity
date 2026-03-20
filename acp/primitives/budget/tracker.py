"""Budget Controls — real-time tracking and hard-stop enforcement (BUD-01…BUD-06)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.config import settings
from acp.models.budget import BudgetAlert, BudgetLimit, BudgetUsage

log = logging.getLogger(__name__)


# ── Window helpers ────────────────────────────────────────────────────────────

def _window_bounds(window: str, now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Return (window_start, window_end) for the given window type."""
    if now is None:
        now = datetime.now(tz=timezone.utc)

    if window == "rolling_24h":
        return now - timedelta(hours=24), now + timedelta(hours=24)
    elif window == "rolling_7d":
        return now - timedelta(days=7), now + timedelta(days=7)
    elif window == "rolling_30d":
        return now - timedelta(days=30), now + timedelta(days=30)
    elif window == "calendar_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # End = first day of next month
        if now.month == 12:
            end = start.replace(year=now.year + 1, month=1)
        else:
            end = start.replace(month=now.month + 1)
        return start, end
    else:
        raise ValueError(f"Unknown window type: {window}")


# ── Core accounting ───────────────────────────────────────────────────────────

async def _get_or_create_usage(
    db: AsyncSession, budget: BudgetLimit
) -> BudgetUsage:
    """Get the current-window usage row, creating it if missing."""
    ws, we = _window_bounds(budget.window)

    result = await db.execute(
        select(BudgetUsage).where(
            BudgetUsage.budget_id == budget.budget_id,
            BudgetUsage.window_start == ws,
        )
    )
    usage = result.scalar_one_or_none()
    if usage is None:
        usage = BudgetUsage(
            budget_id=budget.budget_id,
            window_start=ws,
            window_end=we,
            used_tokens=0,
            used_cost_usd=0.0,
        )
        db.add(usage)
        await db.flush()
    return usage


async def check_budget(
    db: AsyncSession,
    *,
    org_id: str,
    team_id: str,
    agent_id: str,
) -> tuple[bool, Optional[str]]:
    """Check if any budget for this agent/team/org has been hard-stopped.

    Returns (is_allowed, reason_if_blocked).
    """
    # Check agent, team, org budgets in order
    for scope_level, scope_id in [
        ("agent", agent_id),
        ("team", team_id),
        ("org", org_id),
    ]:
        result = await db.execute(
            select(BudgetLimit).where(
                BudgetLimit.org_id == org_id,
                BudgetLimit.scope_level == scope_level,
                BudgetLimit.scope_id == scope_id,
                BudgetLimit.is_active == True,  # noqa: E712
            )
        )
        for budget in result.scalars().all():
            usage = await _get_or_create_usage(db, budget)
            if usage.hard_stopped:
                return False, (
                    f"Budget hard stop active for {scope_level} {scope_id}: "
                    f"${usage.used_cost_usd:.4f} / ${budget.max_cost_usd} used"
                )

    return True, None


async def record_usage(
    db: AsyncSession,
    *,
    org_id: str,
    team_id: str,
    agent_id: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    """Update budget usage counters after a completed LLM call."""
    total_tokens = input_tokens + output_tokens

    for scope_level, scope_id in [
        ("agent", agent_id),
        ("team", team_id),
        ("org", org_id),
    ]:
        result = await db.execute(
            select(BudgetLimit).where(
                BudgetLimit.org_id == org_id,
                BudgetLimit.scope_level == scope_level,
                BudgetLimit.scope_id == scope_id,
                BudgetLimit.is_active == True,  # noqa: E712
            )
        )
        for budget in result.scalars().all():
            usage = await _get_or_create_usage(db, budget)

            if usage.hard_stopped:
                continue

            usage.used_tokens += total_tokens
            usage.used_cost_usd += cost_usd

            # Update per-model breakdown
            breakdown = dict(usage.model_breakdown or {})
            if model_id not in breakdown:
                breakdown[model_id] = {"tokens": 0, "cost_usd": 0.0}
            breakdown[model_id]["tokens"] += total_tokens
            breakdown[model_id]["cost_usd"] += cost_usd
            usage.model_breakdown = breakdown

            # Check hard stop
            should_stop = False
            if budget.max_tokens and usage.used_tokens >= budget.max_tokens:
                should_stop = True
            if budget.max_cost_usd and usage.used_cost_usd >= budget.max_cost_usd:
                should_stop = True

            if should_stop and not usage.hard_stopped:
                usage.hard_stopped = True
                usage.hard_stopped_at = datetime.now(tz=timezone.utc)
                log.warning(
                    "Budget hard stop triggered for %s %s: %.4f USD used",
                    scope_level, scope_id, usage.used_cost_usd,
                )

            await db.flush()

            # Check and send threshold alerts
            await _check_threshold_alerts(db, budget, usage)


async def _check_threshold_alerts(
    db: AsyncSession,
    budget: BudgetLimit,
    usage: BudgetUsage,
) -> None:
    """Send threshold alerts (50%, 80%, 95%, 100%) if not already sent this window."""
    if not budget.max_cost_usd:
        return

    pct_used = (usage.used_cost_usd / budget.max_cost_usd) * 100

    for threshold in budget.alert_thresholds:
        if pct_used < threshold:
            continue

        # Check if already sent for this window+threshold
        already_sent = await db.execute(
            select(BudgetAlert).where(
                BudgetAlert.budget_id == budget.budget_id,
                BudgetAlert.threshold_pct == threshold,
                BudgetAlert.window_start == usage.window_start,
            )
        )
        if already_sent.scalar_one_or_none():
            continue

        # Record alert sent
        alert = BudgetAlert(
            budget_id=budget.budget_id,
            threshold_pct=threshold,
            window_start=usage.window_start,
            channels_notified=budget.alert_channels,
        )
        db.add(alert)
        await db.flush()

        log.info(
            "Budget alert: %d%% threshold crossed for budget %s (%.2f USD)",
            threshold, budget.budget_id, usage.used_cost_usd,
        )

        # TODO: dispatch to notification channels (Slack, webhook)
        # asyncio.create_task(send_budget_alert(budget, usage, threshold))
