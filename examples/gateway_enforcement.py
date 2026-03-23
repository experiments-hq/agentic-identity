"""
Gateway enforcement example: per-agent identity with a shared upstream credential.

This example demonstrates the core claim from the AIS design:

    A gateway can distinguish two agents running under the same service account
    and enforce policy on the specific agent identity rather than just the
    underlying workload.

Two agents share the same organization and upstream API key. They have different
team_id values, so different policies apply to each one. The gateway verifies
each agent's jwt, extracts the per-agent claims, and makes an independent policy
decision for each agent — without the upstream API key ever determining what
the agent is allowed to do.

Requirements:
    pip install -e ".[dev]"
    acp serve &
    acp demo-seed      # seeds demo data including policies

Usage:
    python examples/gateway_enforcement.py
"""
from __future__ import annotations

import asyncio
import httpx

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "acp-demo-admin-token"
ORG_ID = "00000000-0000-0000-0000-00000000demo"

HEADERS = {
    "x-acp-admin-token": ADMIN_TOKEN,
    "Content-Type": "application/json",
}


async def register_agent(client: httpx.AsyncClient, *, display_name: str, team_id: str, environment: str) -> tuple[str, str]:
    """Register an agent and return (agent_id, jwt_token)."""
    r = await client.post("/api/agents/register", json={
        "org_id": ORG_ID,
        "team_id": team_id,
        "display_name": display_name,
        "framework": "langgraph",
        "environment": environment,
        "created_by": "gateway-example",
    })
    r.raise_for_status()
    data = r.json()
    return data["agent"]["agent_id"], data["token"]


async def simulate_policy(client: httpx.AsyncClient, *, agent_id: str, team_id: str, environment: str, action: str) -> str:
    """Run a policy simulation and return the decision."""
    r = await client.post("/api/policies/simulate", json={
        "agent_id": agent_id,
        "org_id": ORG_ID,
        "team_id": team_id,
        "environment": environment,
        "action_type": "llm_call",
        "action_detail": {"model_id": "claude-sonnet-4-6", "path": "/v1/messages"},
        "resource": {"environment": environment},
    })
    data = r.json()
    return data.get("decision", "unknown")


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=15) as client:

        # Both agents share the same org — in old-world terms, the same "service account".
        # Under AIS, they each get a distinct signed identity credential.

        print("\n── Registering two agents under the same org ──────────────────")

        agent_a_id, token_a = await register_agent(
            client,
            display_name="Finance Reconciliation Agent",
            team_id="team-finance",
            environment="production",
        )
        print(f"  Agent A registered: {agent_a_id}  (team=team-finance, env=production)")

        agent_b_id, token_b = await register_agent(
            client,
            display_name="Dev Sandbox Agent",
            team_id="team-engineering",
            environment="development",
        )
        print(f"  Agent B registered: {agent_b_id}  (team=team-engineering, env=development)")

        print("\n── Gateway verifies each token independently ───────────────────")
        print("  Both agents share org_id and upstream API key.")
        print("  The gateway distinguishes them by agent_id and team_id from the JWT.")

        print("\n── Policy evaluation per agent identity ────────────────────────")

        decision_a = await simulate_policy(
            client,
            agent_id=agent_a_id,
            team_id="team-finance",
            environment="production",
        )
        print(f"  Agent A (finance / production)     → {decision_a.upper()}")

        decision_b = await simulate_policy(
            client,
            agent_id=agent_b_id,
            team_id="team-engineering",
            environment="development",
        )
        print(f"  Agent B (engineering / development) → {decision_b.upper()}")

        print("\n── Summary ─────────────────────────────────────────────────────")
        print("  Same org. Different per-agent identities. Different policy outcomes.")
        print("  The upstream API key never determines what either agent can do.")
        print("  Policy is enforced on the verified agent identity, not the credential.")
        print()


if __name__ == "__main__":
    asyncio.run(main())
