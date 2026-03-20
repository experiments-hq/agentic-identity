"""Observability / Trace data models (OBS-01 … OBS-07)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class AgentTrace(Base):
    """Root record for a single agent run — the unit of observability."""

    __tablename__ = "agent_traces"

    trace_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # For multi-agent trees: parent span from the delegating agent
    parent_trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    terminal_state: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )  # success | failure | timeout | blocked

    # Aggregate cost for this trace
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Framework that produced this trace
    framework: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    environment: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    spans: Mapped[list[TraceSpan]] = relationship(
        back_populates="trace", cascade="all, delete-orphan",
        order_by="TraceSpan.started_at",
    )


class TraceSpan(Base):
    """A single step within a trace — one LLM call, tool call, or policy check."""

    __tablename__ = "trace_spans"

    span_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    trace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_traces.trace_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    span_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # llm_call | tool_call | policy_check | agent_delegation

    # What happened
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # LLM call fields
    model_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Inputs / outputs (may be PII-redacted)
    inputs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    outputs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    inputs_redacted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Policy decision at this step
    policy_decision: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    policy_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="ok", nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    trace: Mapped[AgentTrace] = relationship(back_populates="spans")
