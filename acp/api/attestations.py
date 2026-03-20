"""Draft AIS attestation endpoints."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

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
    expired = [challenge_id for challenge_id, payload in _challenges.items() if payload["expires_at"] <= now]
    for challenge_id in expired:
        _challenges.pop(challenge_id, None)


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
    """Issue a short-lived attestation challenge."""
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
async def verify_attestation_response(payload: AttestationResponseRequest):
    """Verify a draft AIS attestation response envelope."""
    _prune_expired_challenges()
    challenge = _challenges.get(payload.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown or expired challenge")
    if challenge["nonce"] != payload.nonce:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge nonce mismatch")
    if not payload.agent_assertion or payload.agent_assertion.count(".") != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent assertion format")
    if not payload.signature.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature is required")

    _challenges.pop(payload.challenge_id, None)

    satisfied_claims = sorted(set(challenge["requested_claims"]).intersection(payload.claims.keys()))
    missing_claims = [claim for claim in challenge["requested_claims"] if claim not in payload.claims]

    return {
        "verified": True,
        "challenge_id": payload.challenge_id,
        "issuer": challenge["issuer"],
        "audience": challenge["audience"],
        "attestation_level": "draft-envelope-verified",
        "requested_claims": challenge["requested_claims"],
        "satisfied_claims": satisfied_claims,
        "missing_claims": missing_claims,
        "received_evidence_type": payload.evidence.get("type"),
    }
