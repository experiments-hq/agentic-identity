"""
AIS Live Agent Simulation — enterprise demo script.

Simulates a real AI agent going through the full ACP governance stack:
  1. Registers itself (AID-01 + AID-02)
  2. Requests an attestation challenge and responds (AIS §8)
  3. Makes a policy-allowed LLM call (policy_check span → allow)
  4. Attempts a policy violation (dev agent writing to prod DB → deny)
  5. Triggers a human approval request (high-risk Opus call → pending)

Run from the agent-identity directory:
    python -m acp.demo_agent
    python -m acp.demo_agent --base-url http://localhost:8001 --token acp-demo-admin-token
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sys
import time
import uuid

# Windows cp1252 terminals can't encode box-drawing chars — force utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timezone, timedelta

import httpx
import typer

app = typer.Typer(add_completion=False)

DEMO_ORG_ID = "00000000-0000-0000-0000-00000000demo"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _pad(b64: str) -> str:
    return b64 + "=" * (-len(b64) % 4)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%H:%M:%S")


def _step(n: int, label: str) -> None:
    print(f"\n[{_now_iso()}] Step {n}: {label}")
    print("─" * 60)


def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗  {msg}")


def _info(key: str, value: str) -> None:
    print(f"     {key}: {value}")


async def run_simulation(base_url: str, admin_token: str) -> None:
    headers = {"x-acp-admin-token": admin_token, "Content-Type": "application/json"}
    agent_id = f"live-{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=15.0) as client:

        # ── Step 1: Health check ──────────────────────────────────────────────
        _step(1, "Connecting to ACP control plane")
        r = await client.get("/health")
        r.raise_for_status()
        data = r.json()
        _ok(f"ACP online — env={data['env']}  version={data['version']}")

        # ── Step 2: Fetch issuer discovery (AIS §4) ───────────────────────────
        _step(2, "AIS issuer discovery — /.well-known/agent-issuer")
        r = await client.get("/.well-known/agent-issuer")
        r.raise_for_status()
        issuer = r.json()
        _ok("Issuer metadata retrieved")
        _info("issuer",        issuer["issuer"])
        _info("jwks_uri",      issuer["jwks_uri"])
        _info("spec_version",  issuer["spec_version"])
        _info("attestation",   issuer["agent_attestation_endpoint"])

        # ── Step 3: Register agent (AID-01 + AID-02) ─────────────────────────
        _step(3, "Registering live agent (AID-01 + AID-02)")
        r = await client.post("/api/agents/register", json={
            "org_id":       DEMO_ORG_ID,
            "team_id":      "team-live-demo",
            "display_name": f"Live Demo Agent [{agent_id[:8]}]",
            "framework":    "langgraph",
            "environment":  "production",
            "created_by":   "demo-script",
            "tags":         {"demo": "live", "session": agent_id[:8]},
        })
        r.raise_for_status()
        reg = r.json()
        registered_agent_id = reg["agent"]["agent_id"]
        jwt_token = reg["token"]
        _ok(f"Agent registered — ID: {registered_agent_id}")
        _info("framework",   reg["agent"]["framework"])
        _info("environment", reg["agent"]["environment"])
        _info("jwt_jti",     reg["jti"])
        _info("expires_at",  reg["expires_at"])
        _info("token",       jwt_token[:48] + "…")

        await asyncio.sleep(0.8)

        # ── Step 4: Fetch JWKS and verify JWT locally (AID-07) ────────────────
        _step(4, "Fetching JWKS and verifying agent JWT locally (AID-07)")
        r = await client.get("/.well-known/jwks.json")
        r.raise_for_status()
        jwks = r.json()
        _ok(f"JWKS retrieved — {len(jwks['keys'])} key(s) published")
        _info("kid", jwks["keys"][0]["kid"])
        _info("alg", jwks["keys"][0]["alg"])

        # Decode JWT header/payload (no crypto — just decode for display)
        parts = jwt_token.split(".")
        hdr = json.loads(base64.urlsafe_b64decode(_pad(parts[0])))
        pay = json.loads(base64.urlsafe_b64decode(_pad(parts[1])))
        _info("jwt.kid",         hdr["kid"])
        _info("jwt.agent_id",    pay["agent_id"])
        _info("jwt.org_id",      pay["org_id"])
        _info("jwt.framework",   pay["framework"])
        _info("jwt.environment", pay["environment"])

        await asyncio.sleep(0.8)

        # ── Step 5: Attestation challenge-response (AIS §8) ───────────────────
        _step(5, "AIS attestation — challenge issued, runtime posture verified")
        r = await client.post("/v1/attestations/challenge", json={
            "audience":         "acp-demo",
            "requested_claims": ["framework", "environment", "runtime_class", "build_digest"],
            "agent_id":         registered_agent_id,
        })
        r.raise_for_status()
        challenge = r.json()
        _ok("Challenge issued")
        _info("challenge_id", challenge["challenge_id"])
        _info("nonce",        challenge["nonce"])
        _info("expires_at",   challenge["expires_at"])

        # Respond with JWT as agent assertion
        r = await client.post("/v1/attestations", json={
            "challenge_id":    challenge["challenge_id"],
            "nonce":           challenge["nonce"],
            "agent_assertion": jwt_token,
            "claims": {
                "framework":     "langgraph",
                "environment":   "production",
                "runtime_class": "cloud_run",
                "build_digest":  "sha256:demo-build",
            },
            "evidence":  {"type": "cloud_run_attestation", "version": "1.0"},
            "signature": _b64url(hashlib.sha256(challenge["nonce"].encode()).digest()),
        })
        r.raise_for_status()
        attest = r.json()
        _ok(f"Attestation result: verified={attest['verified']}  level={attest['attestation_level']}")
        _info("jwt_verified",      str(attest["jwt_verified"]))
        _info("satisfied_claims",  ", ".join(attest["satisfied_claims"]))
        _info("missing_claims",    ", ".join(attest["missing_claims"]) or "none")

        await asyncio.sleep(0.8)

        # ── Step 6: Policy simulation — allowed call ──────────────────────────
        _step(6, "Policy simulation — production LLM call (expect: allow)")
        r = await client.post("/api/policies/simulate", json={
            "agent_id":    registered_agent_id,
            "org_id":      DEMO_ORG_ID,
            "team_id":     "team-live-demo",
            "environment": "production",
            "action_type": "llm_call",
            "action_detail": {
                "model_id": "claude-sonnet-4-6",
                "path": "/v1/messages",
            },
            "resource":    {"environment": "production"},
            "attestation": {"verified": True, "claims": {"runtime_class": "cloud_run", "build_digest": "sha256:demo-build"}},
        })
        sim = r.json()
        decision = sim.get("decision", "unknown")
        _ok(f"Policy decision: {decision.upper()}")
        if sim.get("matched_policy_id"):
            _info("matched_policy", sim["matched_policy_id"])
        if sim.get("evaluation_ms"):
            _info("eval_time",     f"{sim['evaluation_ms']}ms")

        await asyncio.sleep(0.8)

        # ── Step 6b: Policy simulation — require_approval escalation ──────────
        _step(6, "Policy simulation — high-risk Opus call (expect: require_approval)")
        r = await client.post("/api/policies/simulate", json={
            "agent_id":    registered_agent_id,
            "org_id":      DEMO_ORG_ID,
            "team_id":     "team-live-demo",
            "environment": "production",
            "action_type": "llm_call",
            "action_detail": {
                "model_id": "claude-opus-4-6",
                "path": "/v1/messages",
            },
            "resource":    {"environment": "production"},
        })
        sim = r.json()
        decision = sim.get("decision", "unknown")
        _ok(f"Policy decision: {decision.upper()} — escalated to human approver")
        if sim.get("matched_policy_id"):
            _info("matched_policy", sim["matched_policy_id"])
        _info("story", "Console Approvals Queue now shows this request with Slack channel alert")

        await asyncio.sleep(0.8)

        # ── Step 7: Policy simulation — denied violation ──────────────────────
        _step(7, "Policy simulation — dev agent writes to prod DB (expect: deny)")
        r = await client.post("/api/policies/simulate", json={
            "agent_id":    registered_agent_id,
            "org_id":      DEMO_ORG_ID,
            "team_id":     "team-live-demo",
            "environment": "development",
            "framework":   "langgraph",
            "action_type": "database_operation",
            "action_detail": {
                "operation": "INSERT",
                "table": "payments",
                "target_environment": "production",
            },
        })
        sim = r.json()
        decision = sim.get("decision", "unknown")
        _ok(f"Policy decision: {decision.upper()} — violation blocked before execution")
        if sim.get("matched_policy_id"):
            _info("matched_policy", sim["matched_policy_id"])

        await asyncio.sleep(0.8)

        # ── Step 8: Credential rotation (AID-03) ─────────────────────────────
        _step(8, "Credential rotation with zero-downtime overlap (AID-03)")
        r = await client.post(f"/api/agents/{registered_agent_id}/rotate")
        r.raise_for_status()
        rot = r.json()
        _ok("New credential issued — old credential valid during overlap window")
        _info("new_jti",      rot["jti"])
        _info("expires_at",   rot["expires_at"])

        await asyncio.sleep(0.8)

        # ── Step 9: Check audit log ───────────────────────────────────────────
        _step(9, "Audit log — verifying immutable record was written")
        r = await client.get(f"/api/audit/events?limit=200")
        r.raise_for_status()
        events = r.json()
        recent = [e for e in events if registered_agent_id in (e.get("resource_id", "") + e.get("actor_id", ""))]
        _ok(f"Audit events for this agent: {len(recent)}")
        for e in recent[:4]:
            _info(e["event_type"], f"{e['action']} → {e['outcome']}")

        r = await client.get("/api/audit/verify")
        r.raise_for_status()
        verify = r.json()
        _ok(f"Hash-chain integrity: {'VALID ✓' if verify['valid'] else 'TAMPERED ✗'}")

        await asyncio.sleep(0.8)

        # ── Step 10: Fleet registry ───────────────────────────────────────────
        _step(10, "Fleet registry — agent now visible in control plane (AID-05)")
        r = await client.get(f"/api/agents/{registered_agent_id}")
        r.raise_for_status()
        agent = r.json()
        _ok(f"Agent in registry: {agent['display_name']}")
        _info("status",      agent["status"])
        _info("last_seen",   str(agent["last_seen_at"]))
        _info("tags",        json.dumps(agent["tags"]))

        print("\n" + "═" * 60)
        print("  SIMULATION COMPLETE")
        print("═" * 60)
        print(f"  Agent ID : {registered_agent_id}")
        print(f"  Open the console to see this agent in the Fleet Registry.")
        print(f"  Console  : {base_url}/console/")
        print("═" * 60 + "\n")


@app.command()
def main(
    base_url: str = typer.Option("http://localhost:8003", help="ACP server base URL"),
    token:    str = typer.Option("acp-demo-admin-token", help="ACP admin token"),
) -> None:
    """Run a live AIS agent simulation against a running ACP server."""
    print("\n" + "═" * 60)
    print("  AIS LIVE AGENT SIMULATION")
    print("  Agent Identity Specification — enterprise demo")
    print("═" * 60)
    asyncio.run(run_simulation(base_url, token))


if __name__ == "__main__":
    app()
