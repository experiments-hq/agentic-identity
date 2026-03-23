"""Tests for Agent Identity primitive (AID-01…AID-07)."""
import pytest
from httpx import AsyncClient, ASGITransport

from acp.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def setup_db():
    from acp.database import create_all_tables
    await create_all_tables()


async def test_register_agent(client):
    resp = await client.post("/api/agents/register", json={
        "org_id": "org-1",
        "team_id": "team-1",
        "display_name": "Test Agent",
        "framework": "custom",
        "environment": "development",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert data["agent"]["status"] == "active"
    assert data["agent"]["framework"] == "custom"


async def test_fleet_registry(client):
    # Register two agents
    for i in range(2):
        await client.post("/api/agents/register", json={
            "org_id": "org-fleet",
            "team_id": "team-1",
            "display_name": f"Agent {i}",
            "framework": "langgraph",
            "environment": "staging",
        })

    resp = await client.get("/api/agents", params={"org_id": "org-fleet"})
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) >= 2


async def test_credential_rotation(client):
    reg = await client.post("/api/agents/register", json={
        "org_id": "org-rot",
        "team_id": "team-1",
        "display_name": "Rotate Me",
        "framework": "crewai",
        "environment": "development",
    })
    agent_id = reg.json()["agent"]["agent_id"]

    rotate_resp = await client.post(f"/api/agents/{agent_id}/rotate")
    assert rotate_resp.status_code == 200
    new_token = rotate_resp.json()["token"]
    assert new_token  # new JWT issued


async def test_revoke_agent(client):
    reg = await client.post("/api/agents/register", json={
        "org_id": "org-rev",
        "team_id": "team-1",
        "display_name": "Revoke Me",
        "framework": "autogen",
        "environment": "production",
    })
    agent_id = reg.json()["agent"]["agent_id"]

    resp = await client.post(f"/api/agents/{agent_id}/revoke")
    assert resp.status_code == 204

    # Agent should now show as revoked
    get_resp = await client.get(f"/api/agents/{agent_id}")
    assert get_resp.json()["status"] == "revoked"


async def test_jwks_endpoint(client):
    # Register to trigger key creation
    await client.post("/api/agents/register", json={
        "org_id": "org-jwks",
        "team_id": "team-1",
        "display_name": "JWKS Test",
        "framework": "custom",
        "environment": "development",
    })
    resp = await client.get("/.well-known/jwks.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "keys" in data
    assert len(data["keys"]) > 0
    key = data["keys"][0]
    assert key["kty"] == "RSA"
    assert key["alg"] == "RS256"


async def test_agent_issuer_metadata_endpoint(client):
    resp = await client.get("/.well-known/agent-issuer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["issuer"] == "http://test"
    assert data["jwks_uri"] == "http://test/.well-known/jwks.json"
    assert data["agent_registration_endpoint"] == "http://test/api/agents/register"
    assert data["agent_attestation_endpoint"] == "http://test/v1/attestations"
    assert data["supported_assertion_types"] == ["agent+jwt"]
    assert "custom" in data["supported_framework_values"]


async def test_attestation_challenge_and_verify_flow(client):
    # Register a real agent so we have a valid JWT to present
    reg = await client.post("/api/agents/register", json={
        "org_id": "org-attest",
        "team_id": "team-attest",
        "display_name": "Attestation Test Agent",
        "framework": "langgraph",
        "environment": "production",
        "created_by": "test",
    })
    assert reg.status_code == 201
    agent_id = reg.json()["agent"]["agent_id"]
    token = reg.json()["token"]

    challenge_resp = await client.post("/v1/attestations/challenge", json={
        "audience": "http://test/gateway",
        "requested_claims": ["framework", "environment", "build_digest"],
        "agent_id": agent_id,
    })
    assert challenge_resp.status_code == 201
    challenge = challenge_resp.json()
    assert challenge["issuer"] == "http://test"
    assert challenge["requested_claims"] == ["framework", "environment", "build_digest"]

    verify_resp = await client.post("/v1/attestations", json={
        "challenge_id": challenge["challenge_id"],
        "nonce": challenge["nonce"],
        "agent_assertion": token,
        "claims": {
            "framework": "langgraph",
            "environment": "production",
        },
        "evidence": {"type": "workload_identity"},
        "signature": "attestation-envelope-sig",
    })
    assert verify_resp.status_code == 200
    result = verify_resp.json()
    assert result["verified"] is True
    assert result["jwt_verified"] is True
    assert result["attestation_level"] == "assertion_verified"
    assert result["satisfied_claims"] == ["environment", "framework"]
    assert result["missing_claims"] == ["build_digest"]
    assert result["agent_id"] == agent_id
