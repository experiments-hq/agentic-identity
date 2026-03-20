"""Incident Replay API."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.models.audit import ReplaySession
from acp.primitives.replay.session import (
    create_replay_session,
    generate_share_link,
    get_step,
    navigate,
)

router = APIRouter(prefix="/api/replay", tags=["replay"])


class CreateSessionRequest(BaseModel):
    trace_id: str
    created_by: str
    counterfactual: bool = False
    counterfactual_from_step: Optional[int] = None
    counterfactual_overrides: Optional[dict] = None


@router.post("", status_code=201)
async def create_session(
    body: CreateSessionRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """RPL-01: Create a replay session for a trace."""
    try:
        session = await create_replay_session(
            db,
            trace_id=body.trace_id,
            created_by=body.created_by,
            counterfactual=body.counterfactual,
            counterfactual_from_step=body.counterfactual_from_step,
            counterfactual_overrides=body.counterfactual_overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "session_id": session.session_id,
        "trace_id": session.trace_id,
        "total_steps": len(session.step_index),
        "current_step": session.current_step,
        "is_counterfactual": session.is_counterfactual,
        "created_at": session.created_at.isoformat(),
    }


@router.get("/{session_id}/step/{step}")
async def get_step_endpoint(
    session_id: str,
    step: int,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """RPL-02 + RPL-03: Get full data for a specific step."""
    try:
        return await get_step(db, session_id, step)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{session_id}/navigate")
async def navigate_endpoint(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    direction: Optional[str] = Query(None, pattern="^(forward|backward)$"),
    jump_to: Optional[int] = Query(None),
    jump_to_first_violation: bool = Query(False),
    jump_to_terminal: bool = Query(False),
):
    """RPL-02: Navigate the replay session."""
    try:
        return await navigate(
            db,
            session_id,
            direction=direction,
            jump_to=jump_to,
            jump_to_first_violation=jump_to_first_violation,
            jump_to_terminal=jump_to_terminal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{session_id}/share")
async def create_share_link(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    expiry_days: Optional[int] = Query(None),
):
    """RPL-05: Generate a time-limited read-only share link."""
    try:
        token = await generate_share_link(db, session_id, expiry_days=expiry_days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "session_id": session_id,
        "share_token": token,
        "share_url": f"/api/replay/shared/{token}",
    }


@router.get("/shared/{token}")
async def view_shared(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """RPL-05: Read-only access to a shared replay session (current step)."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(ReplaySession).where(ReplaySession.share_token == token)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Share link not found")

    if session.share_expires_at and session.share_expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=410, detail="Share link has expired")

    return await get_step(db, session.session_id, session.current_step)
