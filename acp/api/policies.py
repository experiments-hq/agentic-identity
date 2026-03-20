"""Policy Management API."""
from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.models.policy import Policy, PolicyVersion
from acp.primitives.audit.logger import EventType, log_event
from acp.primitives.policy.dsl import PolicyDSLError, parse_and_compile
from acp.primitives.policy.engine import ActionRequest, policy_engine

router = APIRouter(prefix="/api/policies", tags=["policy"])


class CreatePolicyRequest(BaseModel):
    org_id: str
    scope_level: str  # org | team | agent
    scope_id: str
    dsl_source: str
    created_by: str = "api"


class UpdatePolicyRequest(BaseModel):
    dsl_source: str
    updated_by: str = "api"


class SimulateRequest(BaseModel):
    org_id: str
    agent_id: str
    team_id: str
    environment: str
    action_type: str
    action_detail: dict[str, Any]
    resource: Optional[dict[str, Any]] = None
    attestation: Optional[dict[str, Any]] = None


@router.get("")
async def list_policies(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    org_id: Optional[str] = Query(None),
    scope_level: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    """List policies for the console and operator workflows."""
    q = select(Policy).order_by(Policy.updated_at.desc(), Policy.created_at.desc())
    if org_id:
        q = q.where(Policy.org_id == org_id)
    if scope_level:
        q = q.where(Policy.scope_level == scope_level)
    if is_active is not None:
        q = q.where(Policy.is_active == is_active)

    result = await db.execute(q)
    policies = result.scalars().all()
    return [
        {
            "policy_id": p.policy_id,
            "org_id": p.org_id,
            "scope_level": p.scope_level,
            "scope_id": p.scope_id,
            "description": p.description,
            "current_version": p.current_version,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "created_by": p.created_by,
            "dsl_source": p.dsl_source,
            "compiled": p.compiled,
        }
        for p in policies
    ]


@router.post("", status_code=201)
async def create_policy(
    body: CreatePolicyRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """POL-01: Create and activate a new policy."""
    if body.scope_level not in ("org", "team", "agent"):
        raise HTTPException(status_code=422, detail="scope_level must be org, team, or agent")

    try:
        compiled = parse_and_compile(body.dsl_source)
    except PolicyDSLError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    policy_id = compiled["policy_id"]

    # Check for duplicate
    existing = await db.execute(
        select(Policy).where(Policy.policy_id == policy_id, Policy.org_id == body.org_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Policy '{policy_id}' already exists")

    policy = Policy(
        policy_id=policy_id,
        org_id=body.org_id,
        scope_level=body.scope_level,
        scope_id=body.scope_id,
        description=compiled.get("description", ""),
        dsl_source=body.dsl_source,
        compiled=compiled,
        current_version=1,
        is_active=True,
        created_by=body.created_by,
    )
    db.add(policy)

    # Create initial version record
    version = PolicyVersion(
        policy_id=policy_id,
        version=1,
        dsl_source=body.dsl_source,
        compiled=compiled,
        created_by=body.created_by,
    )
    db.add(version)

    await log_event(
        db,
        event_type=EventType.POLICY_CREATED,
        actor_type="user",
        actor_id=body.created_by,
        resource_type="policy",
        resource_id=policy_id,
        action="create",
        outcome="success",
        payload={"org_id": body.org_id, "scope_level": body.scope_level, "scope_id": body.scope_id},
    )

    return {
        "policy_id": policy_id,
        "version": 1,
        "current_version": 1,
        "scope_level": body.scope_level,
        "scope_id": body.scope_id,
        "is_active": True,
    }


@router.put("/{policy_id}")
async def update_policy(
    policy_id: str,
    body: UpdatePolicyRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """POL-04: Update policy (creates new version)."""
    result = await db.execute(select(Policy).where(Policy.policy_id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    try:
        compiled = parse_and_compile(body.dsl_source)
    except PolicyDSLError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    new_version = policy.current_version + 1
    policy.dsl_source = body.dsl_source
    policy.compiled = compiled
    policy.current_version = new_version

    version = PolicyVersion(
        policy_id=policy_id,
        version=new_version,
        dsl_source=body.dsl_source,
        compiled=compiled,
        created_by=body.updated_by,
    )
    db.add(version)

    await log_event(
        db,
        event_type=EventType.POLICY_UPDATED,
        actor_type="user",
        actor_id=body.updated_by,
        resource_type="policy",
        resource_id=policy_id,
        action="update",
        outcome="success",
        payload={"new_version": new_version},
    )

    return {"policy_id": policy_id, "version": new_version, "current_version": new_version}


@router.post("/{policy_id}/rollback")
async def rollback_policy(
    policy_id: str,
    version: int,
    updated_by: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """POL-04: Rollback to a prior version."""
    result = await db.execute(select(Policy).where(Policy.policy_id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    ver_result = await db.execute(
        select(PolicyVersion).where(
            PolicyVersion.policy_id == policy_id, PolicyVersion.version == version
        )
    )
    ver = ver_result.scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    new_version = policy.current_version + 1
    policy.dsl_source = ver.dsl_source
    policy.compiled = ver.compiled
    policy.current_version = new_version

    rollback_ver = PolicyVersion(
        policy_id=policy_id,
        version=new_version,
        dsl_source=ver.dsl_source,
        compiled=ver.compiled,
        created_by=updated_by,
    )
    db.add(rollback_ver)

    await log_event(
        db,
        event_type=EventType.POLICY_ROLLED_BACK,
        actor_type="user",
        actor_id=updated_by,
        resource_type="policy",
        resource_id=policy_id,
        action="rollback",
        outcome="success",
        payload={"rolled_back_to_version": version, "new_version": new_version},
    )
    return {"policy_id": policy_id, "rolled_back_to": version, "new_version": new_version}


@router.get("/{policy_id}/versions")
async def get_versions(
    policy_id: str,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """POL-04: List all versions of a policy."""
    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version)
    )
    versions = result.scalars().all()
    return [
        {
            "version": v.version,
            "created_at": v.created_at.isoformat(),
            "created_by": v.created_by,
            "dsl_source": v.dsl_source,
        }
        for v in versions
    ]


@router.post("/simulate")
async def simulate(
    body: SimulateRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """POL-07: Simulate a policy evaluation without writing to the decision log."""
    req = ActionRequest(
        agent_id=body.agent_id,
        org_id=body.org_id,
        team_id=body.team_id,
        environment=body.environment,
        action_type=body.action_type,
        action_detail=body.action_detail,
        resource=body.resource,
        attestation=body.attestation,
    )
    decision = await policy_engine.simulate(db, req)
    return {
        "decision": decision.decision,
        "policy_id": decision.policy_id,
        "reason": decision.reason,
        "evaluation_ms": round(decision.evaluation_ms, 2),
    }
