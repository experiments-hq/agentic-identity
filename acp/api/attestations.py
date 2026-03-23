"""AIS attestation endpoints — challenge-response protocol for runtime agent verification."""
from __future__ import annotations

import base64
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.config import settings
from acp.database import get_db_dependency
from acp.models.agent import RSAKeyPair
from acp.primitives.identity.credentials import verify_agent_jwt

router = APIRouter(tags=["attestations"])

_CHALLENGE_TTL = timedelta(minutes=5)
_challenges: dict[str, dict] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _prune_expired_challenges() -> None:
    now = _utcnow()
    expired = [cid for cid, c in _challenges.items() if c["expires_at"] <= now]
    for cid in expired:
        _challenges.pop(cid, None)


class AttestationChallengeRequest(BaseModel):
    audience: str
    requested_claims: list[str] = Field(default_factory=lambda: ["framework", "environment"])
    agent_id: str | None = None


class AttestationResponseRequest(BaseModel):
    challenge_id: str
    nonce: str
    agent_assertion: str
    claims: dict = Field(default_factory=dict)
    evidence: dict = Field(default_factory=dict)
    signature: str


@router.post("/v1/attestations/challenge", status_code=status.HTTP_201_CREATED)
async def create_attestation_challenge(payload: AttestationChallengeRequest, request: Request):
    """Issue a short-lived attestation challenge (AIS §8)."""
    _prune_expired_challenges()
    issued_at = _utcnow()
    challenge_id = str(uuid.uuid4())
    nonce = secrets.token_urlsafe(18)
    expires_at = issued_at + _CHALLENGE_TTL

    _challenges[challenge_id] = {
        "challenge_id": challenge_id,
        "issuer": _base_url(request),
        "audience": payload.audience,
        "nonce": nonce,
        "requested_claims": payload.requested_claims,
        "agent_id": payload.agent_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }

    return {
        "challenge_id": challenge_id,
        "issuer": _base_url(request),
        "audience": payload.audience,
        "nonce": nonce,
        "issued_at": _isoformat(issued_at),
        "expires_at": _isoformat(expires_at),
        "requested_claims": payload.requested_claims,
        "agent_id": payload.agent_id,
    }


@router.post("/v1/attestations")
async def verify_attestation_response(
    payload: AttestationResponseRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """Verify an AIS attestation response — validates the agent assertion JWT against JWKS."""
    _prune_expired_challenges()
    challenge = _challenges.get(payload.challenge_id)
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired challenge",
        )
    if challenge["nonce"] != payload.nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge nonce mismatch",
        )
    if not payload.agent_assertion or payload.agent_assertion.count(".") != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agent_assertion must be a three-part JWT",
        )
    if not payload.signature.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signature is required",
        )

    # ── Verify agent assertion JWT against JWKS ───────────────────────────────
    # This verifies that the assertion was signed by a registered issuer key and
    # that all required AIS claims are present and valid.  It does NOT verify
    # hardware-backed runtime evidence; that requires platform-specific evidence
    # verification which is out of scope for 0.1-draft.
    jwt_verified = False
    jwt_payload: dict = {}
    jwt_error: str | None = None

    try:
        header_part = payload.agent_assertion.split(".")[0]
        header_json = base64.urlsafe_b64decode(header_part + "=" * (-len(header_part) % 4))
        header = json.loads(header_json)
        kid = header.get("kid")

        if not kid:
            raise ValueError("JWT header missing 'kid'")

        key_result = await db.execute(
            select(RSAKeyPair).where(
                RSAKeyPair.key_id == kid,
                RSAKeyPair.is_active == True,  # noqa: E712
            )
        )
        rsa_key = key_result.scalar_one_or_none()
        if not rsa_key:
            raise ValueError(f"No active key found for kid '{kid}'")

        jwt_payload = verify_agent_jwt(
            payload.agent_assertion,
            rsa_key.public_key_pem,
            expected_issuer=settings.issuer_url,
        )
        jwt_verified = True

    except ValueError as exc:
        jwt_error = str(exc)
    except Exception as exc:
        jwt_error = f"JWT parse error: {exc}"

    _challenges.pop(payload.challenge_id, None)

    # JWT must be valid for attestation to succeed
    if not jwt_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Agent assertion verification failed: {jwt_error}",
        )

    # ── Evaluate claims ───────────────────────────────────────────────────────
    satisfied_claims = sorted(
        set(challenge["requested_claims"]).intersection(payload.claims.keys())
    )
    missing_claims = [
        c for c in challenge["requested_claims"] if c not in payload.claims
    ]

    # attestation_level reflects what was actually verified:
    # "assertion_verified" — issuer-signed JWT is valid; claims are self-reported
    # and not backed by hardware or platform attestation evidence in this version.
    attestation_level = "assertion_verified"

    return {
        "verified": True,
        "challenge_id": payload.challenge_id,
        "issuer": challenge["issuer"],
        "audience": challenge["audience"],
        "attestation_level": attestation_level,
        "jwt_verified": jwt_verified,
        "requested_claims": challenge["requested_claims"],
        "satisfied_claims": satisfied_claims,
        "missing_claims": missing_claims,
        "received_evidence_type": payload.evidence.get("type"),
        "agent_id": jwt_payload.get("agent_id"),
        "org_id": jwt_payload.get("org_id"),
        "framework": jwt_payload.get("framework"),
        "environment": jwt_payload.get("environment"),
    }
