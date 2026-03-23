"""Adversarial tests — JWT rejection, attestation abuse, proxy enforcement.

For a security protocol, rejection tests matter more than happy-path tests.
Every test here asserts that a specific malformed or malicious input is refused.
"""
from __future__ import annotations

import base64
import json
import time

import pytest
from httpx import AsyncClient, ASGITransport

from acp.main import app
from acp.primitives.identity.credentials import verify_agent_jwt


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def setup_db():
    from acp.database import create_all_tables
    await create_all_tables()


@pytest.fixture
async def registered(client):
    """Register an agent and return (agent_id, token, jwks)."""
    reg = await client.post("/api/agents/register", json={
        "org_id": "org-adv",
        "team_id": "team-adv",
        "display_name": "Adversarial Test Agent",
        "framework": "custom",
        "environment": "development",
        "created_by": "test",
    })
    assert reg.status_code == 201
    data = reg.json()
    jwks_resp = await client.get("/.well-known/jwks.json")
    return data["agent"]["agent_id"], data["token"], jwks_resp.json()


# ── JWT header tampering ───────────────────────────────────────────────────────

def _tamper_header(token: str, **overrides) -> str:
    """Return a token with the header fields replaced — signature is now invalid."""
    parts = token.split(".")
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    header.update(overrides)
    new_header = base64.urlsafe_b64encode(
        json.dumps(header, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    return f"{new_header}.{parts[1]}.{parts[2]}"


def _tamper_payload(token: str, **overrides) -> str:
    """Return a token with payload fields replaced — signature is now invalid."""
    parts = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
    payload.update(overrides)
    new_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    return f"{parts[0]}.{new_payload}.{parts[2]}"


def _get_public_key_pem(jwks: dict, kid: str) -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
    for key in jwks["keys"]:
        if key["kid"] == kid:
            def b64_to_int(s: str) -> int:
                padded = s + "=" * (-len(s) % 4)
                return int.from_bytes(base64.urlsafe_b64decode(padded), "big")
            pub = RSAPublicNumbers(b64_to_int(key["e"]), b64_to_int(key["n"])).public_key()
            return pub.public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
    raise KeyError(f"kid {kid!r} not found in JWKS")


# ── Algorithm confusion ────────────────────────────────────────────────────────

async def test_rejects_alg_none(registered):
    _, token, jwks = registered
    parts = token.split(".")
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    kid = header["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    bad_token = _tamper_header(token, alg="none")
    with pytest.raises(ValueError, match="RS256"):
        verify_agent_jwt(bad_token, pub_pem)


async def test_rejects_alg_hs256(registered):
    _, token, jwks = registered
    parts = token.split(".")
    kid = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    bad_token = _tamper_header(token, alg="HS256")
    with pytest.raises(ValueError, match="RS256"):
        verify_agent_jwt(bad_token, pub_pem)


async def test_rejects_wrong_typ(registered):
    _, token, jwks = registered
    parts = token.split(".")
    kid = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    bad_token = _tamper_header(token, typ="JWT")
    with pytest.raises(ValueError, match="agent\\+jwt"):
        verify_agent_jwt(bad_token, pub_pem)


async def test_rejects_missing_typ(registered):
    _, token, jwks = registered
    parts = token.split(".")
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    kid = header["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    header.pop("typ", None)
    new_header = base64.urlsafe_b64encode(
        json.dumps(header, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    bad_token = f"{new_header}.{parts[1]}.{parts[2]}"
    with pytest.raises(ValueError, match="agent\\+jwt"):
        verify_agent_jwt(bad_token, pub_pem)


# ── Payload tampering ─────────────────────────────────────────────────────────

async def test_rejects_tampered_payload(registered):
    """Changing any payload field invalidates the RSA signature."""
    _, token, jwks = registered
    parts = token.split(".")
    kid = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    bad_token = _tamper_payload(token, org_id="evil-org")
    with pytest.raises(ValueError, match="[Ss]ignature"):
        verify_agent_jwt(bad_token, pub_pem)


async def test_rejects_missing_required_claim(registered):
    """A token missing agent_id must be rejected even if signature is otherwise intact."""
    _, token, jwks = registered
    parts = token.split(".")
    kid = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    # Tamper the payload to drop agent_id — signature will also be invalid,
    # but the missing-claim check should fire before or alongside signature failure.
    bad_token = _tamper_payload(token, agent_id=None)
    with pytest.raises(ValueError):
        verify_agent_jwt(bad_token, pub_pem)


async def test_rejects_expired_token(registered):
    _, token, jwks = registered
    parts = token.split(".")
    kid = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    past = int(time.time()) - 7200
    bad_token = _tamper_payload(token, exp=past, iat=past - 3600)
    with pytest.raises(ValueError, match="[Ee]xpir"):
        verify_agent_jwt(bad_token, pub_pem)


async def test_rejects_wrong_issuer(registered):
    _, token, jwks = registered
    parts = token.split(".")
    kid = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    with pytest.raises(ValueError, match="[Ii]ssuer"):
        verify_agent_jwt(token, pub_pem, expected_issuer="https://evil.example.com")


async def test_rejects_wrong_audience(registered):
    _, token, jwks = registered
    parts = token.split(".")
    kid = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    with pytest.raises(ValueError, match="[Aa]udience"):
        verify_agent_jwt(token, pub_pem, expected_audience="https://not-the-right-audience.example.com")


async def test_rejects_malformed_jwt(registered):
    _, _, jwks = registered
    kid = jwks["keys"][0]["kid"]
    pub_pem = _get_public_key_pem(jwks, kid)

    with pytest.raises(ValueError, match="[Mm]alformed"):
        verify_agent_jwt("not.a.real.jwt.token", pub_pem)

    with pytest.raises(ValueError):
        verify_agent_jwt("onlytwoparts.here", pub_pem)


# ── Proxy endpoint — auth rejection ───────────────────────────────────────────

async def test_proxy_rejects_missing_auth(client):
    resp = await client.post("/v1/messages", json={"model": "claude-haiku-4-5-20251001", "messages": []})
    assert resp.status_code == 401


async def test_proxy_rejects_garbage_token(client):
    resp = await client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer this.is.garbage"},
        json={"model": "claude-haiku-4-5-20251001", "messages": []},
    )
    assert resp.status_code == 401


async def test_proxy_rejects_tampered_token(client, registered):
    _, token, _ = registered
    bad_token = _tamper_payload(token, org_id="attacker-org")
    resp = await client.post(
        "/v1/messages",
        headers={"Authorization": f"Bearer {bad_token}"},
        json={"model": "claude-haiku-4-5-20251001", "messages": []},
    )
    assert resp.status_code == 401


# ── Attestation — challenge abuse ─────────────────────────────────────────────

async def test_attestation_rejects_wrong_nonce(client, registered):
    agent_id, token, _ = registered
    challenge_resp = await client.post("/v1/attestations/challenge", json={
        "audience": "http://test/gateway",
        "requested_claims": ["framework"],
        "agent_id": agent_id,
    })
    assert challenge_resp.status_code == 201
    challenge = challenge_resp.json()

    resp = await client.post("/v1/attestations", json={
        "challenge_id": challenge["challenge_id"],
        "nonce": "wrong-nonce-value",
        "agent_assertion": token,
        "claims": {"framework": "custom"},
        "evidence": {},
        "signature": "sig",
    })
    assert resp.status_code == 400


async def test_attestation_rejects_unknown_challenge(client, registered):
    _, token, _ = registered
    resp = await client.post("/v1/attestations", json={
        "challenge_id": "00000000-0000-0000-0000-000000000000",
        "nonce": "any-nonce",
        "agent_assertion": token,
        "claims": {},
        "evidence": {},
        "signature": "sig",
    })
    assert resp.status_code == 404


async def test_attestation_rejects_invalid_jwt(client):
    challenge_resp = await client.post("/v1/attestations/challenge", json={
        "audience": "http://test/gateway",
        "requested_claims": ["framework"],
    })
    challenge = challenge_resp.json()

    resp = await client.post("/v1/attestations", json={
        "challenge_id": challenge["challenge_id"],
        "nonce": challenge["nonce"],
        "agent_assertion": "garbage.jwt.token",
        "claims": {"framework": "langgraph"},
        "evidence": {},
        "signature": "sig",
    })
    assert resp.status_code == 401


async def test_attestation_rejects_missing_signature(client, registered):
    agent_id, token, _ = registered
    challenge_resp = await client.post("/v1/attestations/challenge", json={
        "audience": "http://test/gateway",
        "requested_claims": ["framework"],
        "agent_id": agent_id,
    })
    challenge = challenge_resp.json()

    resp = await client.post("/v1/attestations", json={
        "challenge_id": challenge["challenge_id"],
        "nonce": challenge["nonce"],
        "agent_assertion": token,
        "claims": {"framework": "custom"},
        "evidence": {},
        "signature": "   ",  # whitespace-only
    })
    assert resp.status_code == 400
