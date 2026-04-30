"""Session endpoints for lightweight operator authentication."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from acp.config import settings
from acp.database import AsyncSessionLocal

router = APIRouter(prefix="/api/session", tags=["session"])

SESSION_COOKIE = "acp_admin_token"


class LoginRequest(BaseModel):
    token: str


async def _resolve_token(token: str) -> str | None:
    """Return a valid token string if it matches the global admin or a tenant token."""
    if secrets.compare_digest(token, settings.admin_token):
        return settings.admin_token

    from acp.models.tenant import Tenant

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.admin_token == token)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            return tenant.admin_token

    return None


@router.get("/status")
async def session_status(request: Request):
    token = request.cookies.get(SESSION_COOKIE) or request.headers.get("x-acp-admin-token", "")
    valid_token = await _resolve_token(token) if token else None
    return {
        "authenticated": valid_token is not None,
        "mode": "development" if settings.env == "development" else settings.env,
    }


@router.post("/login")
async def session_login(payload: LoginRequest, response: Response):
    valid_token = await _resolve_token(payload.token)
    if not valid_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")

    response.set_cookie(
        key=SESSION_COOKIE,
        value=valid_token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=60 * 60 * 12,
        path="/",
    )
    return {"authenticated": True, "mode": settings.env}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def session_logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return None
