"""Agent Identity Service — registration, credential lifecycle, fleet registry (AID-01…AID-08)."""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from acp.config import settings
from acp.models.agent import Agent, AgentCredential, RSAKeyPair
from acp.primitives.identity.credentials import (
    create_agent_jwt,
    decrypt_private_key,
    generate_rsa_key_pair,
    public_key_to_jwk,
    verify_agent_jwt,
)


# ── In-process revocation cache ───────────────────────────────────────────────
# Maps jti -> revoked_at (epoch seconds). Refreshed every settings.revocation_cache_ttl_seconds.
_revocation_cache: dict[str, float] = {}
_cache_last_refreshed: float = 0.0
_cache_lock = asyncio.Lock()


async def _refresh_revocation_cache(db: AsyncSession) -> None:
    global _cache_last_refreshed
    async with _cache_lock:
        if time.monotonic() - _cache_last_refreshed < settings.revocation_cache_ttl_seconds:
            return
        result = await db.execute(
            select(AgentCredential.jti, AgentCredential.revoked_at).where(
                AgentCredential.is_active == False  # noqa: E712
            )
        )
        _revocation_cache.clear()
        for jti, revoked_at in result.all():
            _revocation_cache[jti] = revoked_at.timestamp() if revoked_at else 0
        _cache_last_refreshed = time.monotonic()


# ── Key management helpers ────────────────────────────────────────────────────

async def _get_or_create_org_key(db: AsyncSession, org_id: str) -> RSAKeyPair:
    result = await db.execute(
        select(RSAKeyPair).where(
            RSAKeyPair.org_id == org_id, RSAKeyPair.is_active == True  # noqa: E712
        )
    )
    key = result.scalar_one_or_none()
    if key:
        try:
            # Validate that the current ACP secret can still decrypt the stored
            # private key. This keeps local/demo environments from getting stuck
            # if the secret changes while a persisted SQLite DB remains.
            decrypt_private_key(key.private_key_encrypted)
            return key
        except Exception:
            key.is_active = False
            await db.flush()

    key_id, public_pem, encrypted_priv = generate_rsa_key_pair()
    key = RSAKeyPair(
        key_id=key_id,
        org_id=org_id,
        public_key_pem=public_pem,
        private_key_encrypted=encrypted_priv,
    )
    db.add(key)
    await db.flush()
    return key


# ── Registration ──────────────────────────────────────────────────────────────

async def register_agent(
    db: AsyncSession,
    *,
    org_id: str,
    team_id: str,
    display_name: str,
    framework: str,
    environment: str,
    created_by: str,
    tags: Optional[dict] = None,
    agent_id: Optional[str] = None,
) -> tuple[Agent, AgentCredential, str]:
    """Register a new agent and issue its first JWT credential.

    Returns (agent, credential, jwt_token_string).
    """
    agent = Agent(
        agent_id=agent_id or str(uuid.uuid4()),
        org_id=org_id,
        team_id=team_id,
        display_name=display_name,
        framework=framework,
        environment=environment,
        created_by=created_by,
        status="active",
        tags=tags or {},
    )
    db.add(agent)
    await db.flush()

    cred, token = await _issue_credential(db, agent)
    return agent, cred, token


async def _issue_credential(
    db: AsyncSession,
    agent: Agent,
    expiry_hours: Optional[int] = None,
) -> tuple[AgentCredential, str]:
    key = await _get_or_create_org_key(db, agent.org_id)

    token, jti, expires_at = create_agent_jwt(
        agent_id=agent.agent_id,
        org_id=agent.org_id,
        team_id=agent.team_id,
        framework=agent.framework,
        environment=agent.environment,
        key_id=key.key_id,
        private_key_encrypted=key.private_key_encrypted,
        expiry_hours=expiry_hours,
    )

    cred = AgentCredential(
        jti=jti,
        agent_id=agent.agent_id,
        expires_at=expires_at,
        public_key_id=key.key_id,
        is_active=True,
    )
    db.add(cred)
    await db.flush()
    return cred, token


# ── Credential rotation (AID-03) ──────────────────────────────────────────────

async def rotate_credential(
    db: AsyncSession,
    agent_id: str,
    overlap_hours: Optional[int] = None,
) -> tuple[AgentCredential, str]:
    """Issue a new credential while keeping the old one valid for overlap_hours."""
    result = await db.execute(
        select(Agent).where(Agent.agent_id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    if agent.status != "active":
        raise ValueError(f"Agent {agent_id} is {agent.status}")

    new_cred, token = await _issue_credential(db, agent)

    overlap = overlap_hours or settings.jwt_rotation_overlap_hours
    overlap_until = datetime.now(tz=timezone.utc) + timedelta(hours=overlap)

    # Mark old credentials as expiring after overlap (don't revoke yet)
    old_creds_result = await db.execute(
        select(AgentCredential).where(
            AgentCredential.agent_id == agent_id,
            AgentCredential.is_active == True,  # noqa: E712
            AgentCredential.jti != new_cred.jti,
        )
    )
    for old_cred in old_creds_result.scalars().all():
        # Shorten expiry to end of overlap window if it's later
        overlap_cutoff = overlap_until
        if old_cred.expires_at.tzinfo is None:
            overlap_cutoff = overlap_until.replace(tzinfo=None)
        if old_cred.expires_at > overlap_cutoff:
            old_cred.expires_at = overlap_cutoff
        await db.flush()

    return new_cred, token


# ── Revocation (AID-04) ───────────────────────────────────────────────────────

async def revoke_credential(
    db: AsyncSession,
    jti: str,
    reason: str = "manual_revocation",
) -> None:
    """Immediately revoke a credential. Propagates to cache within TTL."""
    result = await db.execute(
        select(AgentCredential).where(AgentCredential.jti == jti)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise ValueError(f"Credential {jti} not found")

    cred.is_active = False
    cred.revoked_at = datetime.now(tz=timezone.utc)
    cred.revocation_reason = reason
    await db.flush()

    # Immediately update local cache
    _revocation_cache[jti] = time.time()


async def revoke_agent(
    db: AsyncSession,
    agent_id: str,
    reason: str = "agent_revoked",
) -> None:
    """Revoke all credentials for an agent and mark it revoked."""
    result = await db.execute(
        select(Agent).where(Agent.agent_id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    agent.status = "revoked"

    creds_result = await db.execute(
        select(AgentCredential).where(
            AgentCredential.agent_id == agent_id,
            AgentCredential.is_active == True,  # noqa: E712
        )
    )
    for cred in creds_result.scalars().all():
        cred.is_active = False
        cred.revoked_at = datetime.now(tz=timezone.utc)
        cred.revocation_reason = reason
        _revocation_cache[cred.jti] = time.time()

    await db.flush()


# ── Authentication (used by proxy) ────────────────────────────────────────────

async def authenticate_request(
    db: AsyncSession,
    bearer_token: str,
) -> dict:
    """Validate an agent JWT from the Authorization header.

    Returns decoded payload dict.
    Raises ValueError with reason on any failure.
    """
    await _refresh_revocation_cache(db)

    # Peek at kid without full verification
    import base64, json as _json

    parts = bearer_token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token")

    try:
        header_json = base64.urlsafe_b64decode(parts[0] + "==")
        header = _json.loads(header_json)
        kid = header.get("kid")
    except Exception:
        raise ValueError("Cannot parse token header")

    # Load public key by kid
    key_result = await db.execute(
        select(RSAKeyPair).where(RSAKeyPair.key_id == kid)
    )
    key = key_result.scalar_one_or_none()
    if not key:
        raise ValueError(f"Unknown key ID: {kid}")

    payload = verify_agent_jwt(bearer_token, key.public_key_pem)

    jti = payload.get("jti")
    if jti in _revocation_cache:
        raise ValueError("Credential has been revoked")

    # Check credential record is still active in DB
    cred_result = await db.execute(
        select(AgentCredential).where(
            AgentCredential.jti == jti,
            AgentCredential.is_active == True,  # noqa: E712
        )
    )
    if not cred_result.scalar_one_or_none():
        raise ValueError("Credential inactive or not found")

    # Update last_seen
    await db.execute(
        update(Agent)
        .where(Agent.agent_id == payload["agent_id"])
        .values(last_seen_at=datetime.now(tz=timezone.utc))
    )

    return payload


# ── JWKS (AID-07) ─────────────────────────────────────────────────────────────

async def get_jwks(db: AsyncSession, org_id: Optional[str] = None) -> dict:
    """Return JWKS document for all active org keys (or a specific org)."""
    query = select(RSAKeyPair).where(RSAKeyPair.is_active == True)  # noqa: E712
    if org_id:
        query = query.where(RSAKeyPair.org_id == org_id)

    result = await db.execute(query)
    keys = result.scalars().all()

    return {
        "keys": [public_key_to_jwk(k.key_id, k.public_key_pem) for k in keys]
    }


# ── Fleet registry (AID-05) ───────────────────────────────────────────────────

async def list_agents(
    db: AsyncSession,
    *,
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    status: Optional[str] = None,
    framework: Optional[str] = None,
    environment: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Agent]:
    q = select(Agent)
    if org_id:
        q = q.where(Agent.org_id == org_id)
    if team_id:
        q = q.where(Agent.team_id == team_id)
    if status:
        q = q.where(Agent.status == status)
    if framework:
        q = q.where(Agent.framework == framework)
    if environment:
        q = q.where(Agent.environment == environment)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())
