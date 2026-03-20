"""Tests for Policy Engine (POL-01…POL-07)."""
import pytest
from httpx import AsyncClient, ASGITransport

from acp.main import app

DENY_DEV_PROD_DB = """
policy_id: "no-prod-db-writes-from-dev-agents"
description: "Development agents cannot write to production databases"
version: 1
subject:
  agent_environment: development
action:
  type: database_operation
  operations: [INSERT, UPDATE, DELETE, DROP]
resource:
  environment: production
outcome: deny
alert:
  severity: critical
  channels: [slack]
"""

ALLOW_LLM = """
policy_id: "allow-llm-calls"
description: "Allow all LLM calls"
subject: {}
action:
  type: llm_call
outcome: allow
"""

ALLOW_ATTESTED_PROD = """
policy_id: "allow-attested-prod-agents"
description: "Allow prod LLM calls only when runtime attestation is verified"
subject:
  agent_environment: production
action:
  type: llm_call
conditions:
  attestation:
    verified: true
    claims:
      runtime_class: cloud_run
      build_digest: sha256:demo-build
    required_claims: [runtime_class, build_digest]
outcome: allow
"""


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def setup_db():
    from acp.database import create_all_tables
    await create_all_tables()


async def test_create_policy(client):
    resp = await client.post("/api/policies", json={
        "org_id": "org-1",
        "scope_level": "org",
        "scope_id": "org-1",
        "dsl_source": DENY_DEV_PROD_DB,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["policy_id"] == "no-prod-db-writes-from-dev-agents"
    assert data["current_version"] == 1


async def test_invalid_dsl_rejected(client):
    resp = await client.post("/api/policies", json={
        "org_id": "org-1",
        "scope_level": "org",
        "scope_id": "org-1",
        "dsl_source": "not: valid: yaml: [[[",
    })
    assert resp.status_code == 422


async def test_policy_versioning(client):
    # Create
    await client.post("/api/policies", json={
        "org_id": "org-ver",
        "scope_level": "org",
        "scope_id": "org-ver",
        "dsl_source": ALLOW_LLM,
    })
    # Update
    updated_dsl = ALLOW_LLM.replace("Allow all LLM calls", "Allow all LLM calls v2")
    resp = await client.put("/api/policies/allow-llm-calls", json={
        "org_id": "org-ver",
        "scope_level": "org",
        "scope_id": "org-ver",
        "dsl_source": updated_dsl,
    })
    assert resp.status_code == 200
    assert resp.json()["current_version"] == 2

    # Versions list
    versions_resp = await client.get("/api/policies/allow-llm-calls/versions")
    assert versions_resp.status_code == 200
    assert len(versions_resp.json()) == 2


async def test_simulate_deny(client):
    await client.post("/api/policies", json={
        "org_id": "org-sim",
        "scope_level": "org",
        "scope_id": "org-sim",
        "dsl_source": DENY_DEV_PROD_DB,
    })
    resp = await client.post("/api/policies/simulate", json={
        "agent_id": "agent-123",
        "org_id": "org-sim",
        "team_id": "team-1",
        "environment": "development",
        "action_type": "database_operation",
        "action_detail": {"operation": "INSERT", "table": "payments"},
        "resource": {"environment": "production"},
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["decision"] == "deny"
    assert result["policy_id"] == "no-prod-db-writes-from-dev-agents"


async def test_default_deny_no_policy(client):
    """POL-03 — No matching policy → deny."""
    resp = await client.post("/api/policies/simulate", json={
        "agent_id": "agent-no-policy",
        "org_id": "org-empty",
        "team_id": "team-1",
        "environment": "production",
        "action_type": "api_call",
        "action_detail": {"endpoint": "/payments/charge"},
    })
    assert resp.status_code == 200
    assert resp.json()["decision"] == "deny"


async def test_attestation_condition_denies_without_verified_posture(client):
    await client.post("/api/policies", json={
        "org_id": "org-attest",
        "scope_level": "org",
        "scope_id": "org-attest",
        "dsl_source": ALLOW_ATTESTED_PROD,
    })
    resp = await client.post("/api/policies/simulate", json={
        "agent_id": "agent-prod-1",
        "org_id": "org-attest",
        "team_id": "team-1",
        "environment": "production",
        "action_type": "llm_call",
        "action_detail": {"model_id": "claude-opus-4-6"},
        "attestation": {
            "verified": False,
            "claims": {
                "runtime_class": "cloud_run",
                "build_digest": "sha256:demo-build",
            },
        },
    })
    assert resp.status_code == 200
    assert resp.json()["decision"] == "deny"


async def test_attestation_condition_allows_when_claims_match(client):
    await client.post("/api/policies", json={
        "org_id": "org-attest-ok",
        "scope_level": "org",
        "scope_id": "org-attest-ok",
        "dsl_source": ALLOW_ATTESTED_PROD,
    })
    resp = await client.post("/api/policies/simulate", json={
        "agent_id": "agent-prod-2",
        "org_id": "org-attest-ok",
        "team_id": "team-1",
        "environment": "production",
        "action_type": "llm_call",
        "action_detail": {"model_id": "claude-opus-4-6"},
        "attestation": {
            "verified": True,
            "claims": {
                "runtime_class": "cloud_run",
                "build_digest": "sha256:demo-build",
            },
        },
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["decision"] == "allow"
    assert result["policy_id"] == "allow-attested-prod-agents"
