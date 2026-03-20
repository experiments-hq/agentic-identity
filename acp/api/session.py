"""Session endpoints for lightweight operator authentication."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from acp.config import settings

router = APIRouter(prefix="/api/session", tags=["session"])

SESSION_COOKIE = "acp_admin_token"


class LoginRequest(BaseModel):
    token: str


@router.get("/status")
async def session_status(request: Request):
    token = request.cookies.get(SESSION_COOKIE) or request.headers.get("x-acp-admin-token", "")
    return {
        "authenticated": secrets.compare_digest(token, settings.admin_token),
        "mode": "development" if settings.env == "development" else settings.env,
    }


@router.post("/login")
async def session_login(payload: LoginRequest, response: Response):
    if not secrets.compare_digest(payload.token, settings.admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")

    response.set_cookie(
        key=SESSION_COOKIE,
        value=settings.admin_token,
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
