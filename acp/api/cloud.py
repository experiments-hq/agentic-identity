"""ACP Cloud — public signup and tenant management."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.models.tenant import Tenant

router = APIRouter(prefix="/api/cloud", tags=["cloud"])


class SignupRequest(BaseModel):
    org_name: str = Field(..., min_length=1, max_length=128)
    email: str = Field(..., min_length=3, max_length=256)
    seed_demo: bool = Field(default=True, description="Seed demo data for the new org")


class SignupResponse(BaseModel):
    org_id: str
    admin_token: str
    issuer_url: str
    jwks_url: str
    registration_endpoint: str
    console_url: str


@router.post("/signup", response_model=SignupResponse, status_code=201)
async def signup(
    body: SignupRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """Public signup — creates an isolated org with its own admin token."""
    existing = await db.execute(
        select(Tenant).where(Tenant.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    org_id = str(uuid.uuid4())
    tenant = Tenant(org_id=org_id, org_name=body.org_name, email=body.email)
    db.add(tenant)
    await db.flush()

    if body.seed_demo:
        from acp.demo import seed_demo_data_for_org

        await seed_demo_data_for_org(db, org_id=org_id)

    base_url = str(request.base_url).rstrip("/")

    return SignupResponse(
        org_id=org_id,
        admin_token=tenant.admin_token,
        issuer_url=base_url,
        jwks_url=f"{base_url}/.well-known/jwks.json",
        registration_endpoint=f"{base_url}/api/agents/register",
        console_url=f"{base_url}/console/",
    )
