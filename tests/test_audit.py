"""Tests for Audit log integrity (AUD-01, AUD-06)."""
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


async def test_audit_events_written_on_registration(client):
    await client.post("/api/agents/register", json={
        "org_id": "org-audit",
        "team_id": "team-1",
        "display_name": "Audit Test",
        "framework": "custom",
        "environment": "development",
    })
    resp = await client.get("/api/audit/events", params={"event_type": "agent.registered", "limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    # endpoint returns {"events": [...], "count": N}
    events = data["events"] if isinstance(data, dict) else data
    assert len(events) >= 1


async def test_chain_integrity_valid(client):
    # Write a few events via agent registration
    for i in range(3):
        await client.post("/api/agents/register", json={
            "org_id": f"org-chain-{i}",
            "team_id": "team-1",
            "display_name": f"Agent {i}",
            "framework": "custom",
            "environment": "development",
        })

    resp = await client.get("/api/audit/verify")
    assert resp.status_code == 200
    result = resp.json()
    assert result["valid"] is True
    assert result["tampered_event_id"] is None


async def test_export_csv(client):
    await client.post("/api/agents/register", json={
        "org_id": "org-csv",
        "team_id": "team-1",
        "display_name": "CSV Test",
        "framework": "custom",
        "environment": "development",
    })
    resp = await client.get("/api/audit/events", params={"format": "csv", "limit": 100})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "event_id" in resp.text
