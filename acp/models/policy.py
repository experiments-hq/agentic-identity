"""Policy Engine data models (POL-01 … POL-08)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # Scope: may be org_id, team_id, or agent_id — level field disambiguates
    scope_level: Mapped[str] = mapped_column(String(16), nullable=False)  # org|team|agent
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Serialised YAML DSL source (human-readable)
    dsl_source: Mapped[str] = mapped_column(Text, nullable=False)
    # Parsed / compiled policy as JSON for fast evaluation
    compiled: Mapped[dict] = mapped_column(JSON, nullable=False)

    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

    versions: Mapped[list[PolicyVersion]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", order_by="PolicyVersion.version"
    )


class PolicyVersion(Base):
    """Append-only version history for each policy (POL-04)."""

    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("policies.policy_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    dsl_source: Mapped[str] = mapped_column(Text, nullable=False)
    compiled: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

    policy: Mapped[Policy] = relationship(back_populates="versions")


class PolicyDecisionLog(Base):
    """Every policy evaluation result (feeds Observability + Audit)."""

    __tablename__ = "policy_decision_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action_detail: Mapped[dict] = mapped_column(JSON, nullable=False)
    matched_policy_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # allow|deny|require_approval
    decision_reason: Mapped[str] = mapped_column(String(512), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    evaluation_ms: Mapped[Optional[float]] = mapped_column(nullable=True)
