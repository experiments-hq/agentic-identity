"""Budget Controls data models (BUD-01 … BUD-06)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class BudgetLimit(Base):
    """Defines a budget for an org, team, or agent over a time window."""

    __tablename__ = "budget_limits"

    budget_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Scope
    scope_level: Mapped[str] = mapped_column(String(16), nullable=False)  # org|team|agent
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Limits
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Rolling window
    window: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # rolling_24h | rolling_7d | rolling_30d | calendar_month

    # Alert thresholds (percentages: 50, 80, 95, 100)
    alert_thresholds: Mapped[list] = mapped_column(
        JSON, default=lambda: [50, 80, 95, 100], nullable=False
    )
    alert_channels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

    usages: Mapped[list[BudgetUsage]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )
    alerts_sent: Mapped[list[BudgetAlert]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )


class BudgetUsage(Base):
    """Running token/cost total for a budget within the current window."""

    __tablename__ = "budget_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("budget_limits.budget_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    used_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Per-model breakdown
    model_breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    hard_stopped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hard_stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    budget: Mapped[BudgetLimit] = relationship(back_populates="usages")


class BudgetAlert(Base):
    """Record of a budget threshold alert that was sent (prevents duplicates)."""

    __tablename__ = "budget_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("budget_limits.budget_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    channels_notified: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    budget: Mapped[BudgetLimit] = relationship(back_populates="alerts_sent")
