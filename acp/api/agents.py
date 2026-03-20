"""Agent Identity API — registration, credential lifecycle, fleet registry."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.models.agent import Agent
from acp.primitives.audit.logger import EventType, log_event
from acp.primitives.identity.service import (
    get_jwks,
    list_agents,
    register_agent,
    revoke_agent,
    revoke_credential,
    rotate_credential,
)

router = APIRouter(prefix="/api/agents", tags=["identity"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterAgentRequest(BaseModel):
    org_id: str
    team_id: str
    display_name: str = Field(..., max_length=128)
    framework: str = Field(..., pattern="^(openclaw|nemoclaw|langgraph|crewai|autogen|custom)$")
    environment: str = Field(..., pattern="^(development|staging|production)$")
    created_by: Optional[str] = "api"
    tags: Optional[dict] = None
    agent_id: Optional[str] = None


class AgentOut(BaseModel):
    agent_id: str
    display_name: str
    org_id: str
    team_id: str
    framework: str
    environment: str
    status: str


class RegisterAgentResponse(BaseModel):
    agent: AgentOut
    jti: str
    expires_at: str
    token: str  # JWT — show once, not stored


class RotateResponse(BaseModel):
    jti: str
    expires_at: str
    token: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=RegisterAgentResponse, status_code=201, include_in_schema=False)
@router.post("/register", response_model=RegisterAgentResponse, status_code=201)
async def register(
    body: RegisterAgentRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """AID-01 + AID-02: Register agent and issue first JWT credential."""
    agent, cred, token = await register_agent(
        db,
        org_id=body.org_id,
        team_id=body.team_id,
        display_name=body.display_name,
        framework=body.framework,
        environment=body.environment,
        created_by=body.created_by or "api",
        tags=body.tags,
        agent_id=body.agent_id,
    )
    await log_event(
        db,
        event_type=EventType.AGENT_REGISTERED,
        actor_type="user",
        actor_id=body.created_by or "api",
        resource_type="agent",
        resource_id=agent.agent_id,
        action="register",
        outcome="success",
        payload={
            "org_id": body.org_id,
            "team_id": body.team_id,
            "framework": body.framework,
            "environment": body.environment,
        },
    )
    return RegisterAgentResponse(
        agent=AgentOut(
            agent_id=agent.agent_id,
            display_name=agent.display_name,
            org_id=agent.org_id,
            team_id=agent.team_id,
            framework=agent.framework,
            environment=agent.environment,
            status=agent.status,
        ),
        jti=cred.jti,
        expires_at=cred.expires_at.isoformat(),
        token=token,
    )


@router.get("", response_model=list[dict])
async def list_fleet(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """AID-05: Fleet registry query."""
    agents = await list_agents(
        db,
        org_id=org_id,
        team_id=team_id,
        status=status,
        framework=framework,
        environment=environment,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "agent_id": a.agent_id,
            "display_name": a.display_name,
            "org_id": a.org_id,
            "team_id": a.team_id,
            "framework": a.framework,
            "environment": a.environment,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
            "tags": a.tags,
        }
        for a in agents
    ]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """Get a single agent by ID."""
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return {
        "agent_id": agent.agent_id,
        "display_name": agent.display_name,
        "org_id": agent.org_id,
        "team_id": agent.team_id,
        "framework": agent.framework,
        "environment": agent.environment,
        "status": agent.status,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
        "tags": agent.tags,
    }


@router.post("/{agent_id}/rotate", response_model=RotateResponse)
async def rotate(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    overlap_hours: Optional[int] = Query(None),
):
    """AID-03: Rotate agent credential with zero-downtime overlap."""
    try:
        cred, token = await rotate_credential(db, agent_id, overlap_hours=overlap_hours)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    await log_event(
        db,
        event_type=EventType.CREDENTIAL_ROTATED,
        actor_type="user",
        actor_id="api",
        resource_type="credential",
        resource_id=cred.jti,
        action="rotate",
        outcome="success",
        payload={"agent_id": agent_id},
    )
    return RotateResponse(
        jti=cred.jti,
        expires_at=cred.expires_at.isoformat(),
        token=token,
    )


@router.post("/{agent_id}/revoke", status_code=204)
async def revoke(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    reason: str = Query("manual_revocation"),
):
    """AID-04: Revoke all credentials for an agent."""
    try:
        await revoke_agent(db, agent_id, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    await log_event(
        db,
        event_type=EventType.AGENT_REVOKED,
        actor_type="user",
        actor_id="api",
        resource_type="agent",
        resource_id=agent_id,
        action="revoke",
        outcome="success",
        payload={"reason": reason},
    )


@router.post("/credentials/{jti}/revoke", status_code=204)
async def revoke_cred(
    jti: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    reason: str = Query("manual_revocation"),
):
    """Revoke a specific credential by JTI."""
    try:
        await revoke_credential(db, jti, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    await log_event(
        db,
        event_type=EventType.CREDENTIAL_REVOKED,
        actor_type="user",
        actor_id="api",
        resource_type="credential",
        resource_id=jti,
        action="revoke",
        outcome="success",
        payload={"reason": reason},
    )


@router.get("/.well-known/jwks.json", include_in_schema=False)
@router.get("/jwks")
async def jwks(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    org_id: Optional[str] = Query(None),
):
    """AID-07: JWKS endpoint for distributed credential verification."""
    return await get_jwks(db, org_id=org_id)
