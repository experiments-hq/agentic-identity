"""Cloud tenant model — tracks signups and per-tenant admin tokens."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _generate_token() -> str:
    return f"acp_cloud_{secrets.token_urlsafe(32)}"


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )
    org_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    admin_token: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True, default=_generate_token
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
