"""Approvals Engine data models (APR-01 … APR-06)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    request_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Full context of the action that triggered approval
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action_detail: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Who (human user, if any) requested this action
    requesting_user: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False, index=True
    )  # pending | approved | denied | timed_out | escalated

    # Approval config from policy
    timeout_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    escalate_to: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    timeout_action: Mapped[str] = mapped_column(String(32), default="deny", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Decision fields (populated when resolved)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    approval_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Notification state
    notified_channels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    decisions: Mapped[list[ApprovalDecision]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class ApprovalDecision(Base):
    """Individual decision event (approve/deny/escalate) on an ApprovalRequest."""

    __tablename__ = "approval_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approval_requests.request_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # approve|deny|escalate
    actor: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    request: Mapped[ApprovalRequest] = relationship(back_populates="decisions")
