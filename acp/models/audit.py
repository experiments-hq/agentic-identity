"""Audit & Compliance data models (AUD-01 … AUD-06)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditEvent(Base):
    """Immutable, cryptographically chained audit log entry (AUD-01, AUD-02)."""

    __tablename__ = "audit_events"

    # Append-only: never UPDATE or DELETE rows in this table.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True,
        default=lambda: str(uuid.uuid4()),
    )

    # AUD-02: required fields
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Microsecond-precision ISO 8601 timestamp stored as string to avoid rounding
    timestamp: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user|agent|system
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)  # success|failure|blocked
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Full event payload as JSON
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Hash chain integrity (AUD-06)
    # SHA-256( previous_hash || event_id || event_type || timestamp || payload_json )
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # GENESIS entry has previous_hash = "0" * 64


class ReplaySession(Base):
    """Incident Replay session (RPL-01 … RPL-05)."""

    __tablename__ = "replay_sessions"

    session_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Shareable link token (RPL-05)
    share_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    share_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Current step pointer for step-through navigation
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Whether this is a counterfactual run (RPL-04)
    is_counterfactual: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    counterfactual_from_step: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Counterfactual overrides as JSON {step_index: modified_input}
    counterfactual_overrides: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Cached ordered list of span_ids for this trace (populated on session create)
    step_index: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
