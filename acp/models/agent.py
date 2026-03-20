"""Agent Identity data models (AID-01 … AID-08)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    framework: Mapped[str] = mapped_column(String(32), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    credentials: Mapped[list[AgentCredential]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", lazy="select"
    )


class AgentCredential(Base):
    """JWT credential record. One active credential per agent at a time; during
    rotation there may be two (overlap window)."""

    __tablename__ = "agent_credentials"

    jti: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    public_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="credentials")


class RSAKeyPair(Base):
    """Org-scoped RSA key pairs used to sign / verify agent JWTs."""

    __tablename__ = "rsa_key_pairs"

    key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    # Private key is stored encrypted with ACP_SECRET_KEY (AES-256-GCM).
    private_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
