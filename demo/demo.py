#!/usr/bin/env python3
"""
AIS Protocol Demo
=================

Demonstrates the complete Agent Identity Specification (AIS) flow —
the same class of protocol OpenID Connect established for user identity,
adapted for autonomous AI agents.

  [1] Discover issuer          GET /.well-known/agent-issuer
  [2] Retrieve JWKS            GET /.well-known/jwks.json
  [3] Register agent           POST /api/agents/register  →  agent+jwt
  [4] Decode token offline     no network call required
  [5] Attest                   POST /v1/attestations/challenge
                               POST /v1/attestations  (JWT signature verified)

Usage:

    # Self-contained (no server needed):
    python demo.py

    # Against a live ACP server:
    python demo.py --url http://localhost:8000

"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
from typing import Any

import httpx

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ── Console helpers ────────────────────────────────────────────────────────────

if HAS_RICH:
    console = Console(legacy_windows=False)

    def header(text: str) -> None:
        console.print()
        console.print(Panel(f"[bold cyan]{text}[/bold cyan]", expand=False))

    def step(n: int, label: str) -> None:
        console.print(f"\n[bold white][ {n} ][/bold white] [bold yellow]{label}[/bold yellow]")

    def ok(msg: str) -> None:
        console.print(f"  [bold green]OK[/bold green]  {msg}")

    def info(msg: str) -> None:
        console.print(f"       [dim]{msg}[/dim]")

    def show_json(data: Any, title: str = "") -> None:
        pretty = json.dumps(data, indent=2)
        console.print(Syntax(pretty, "json", theme="monokai", line_numbers=False))

    def show_table(rows: list[tuple[str, str]], title: str = "") -> None:
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        t.add_column(style="dim")
        t.add_column(style="bold white")
        for k, v in rows:
            t.add_row(k, v)
        if title:
            console.print(f"  [dim]{title}[/dim]")
        console.print(t)

    def error(msg: str) -> None:
        console.print(f"  [bold red]ERR[/bold red]  {msg}")

else:
    def header(text: str) -> None:
        print(f"\n=== {text} ===")

    def step(n: int, label: str) -> None:
        print(f"\n[{n}] {label}")

    def ok(msg: str) -> None:
        print(f"  OK  {msg}")

    def info(msg: str) -> None:
        print(f"      {msg}")

    def show_json(data: Any, title: str = "") -> None:
        print(json.dumps(data, indent=2))

    def show_table(rows: list[tuple[str, str]], title: str = "") -> None:
        for k, v in rows:
            print(f"  {k:24s} {v}")

    def error(msg: str) -> None:
        print(f"  ERR {msg}")


# ── JWT decode helper (offline, no network) ───────────────────────────────────

def _b64_decode(segment: str) -> bytes:
    segment += "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment)


def decode_jwt_parts(token: str) -> tuple[dict, dict]:
    """Return (header, payload) decoded from a JWT without verifying."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Not a three-part JWT")
    header = json.loads(_b64_decode(parts[0]))
    payload = json.loads(_b64_decode(parts[1]))
    return header, payload


# ── Demo flow ─────────────────────────────────────────────────────────────────

async def run_demo(client: httpx.AsyncClient, base_url: str) -> None:

    header("Agent Identity Specification — Protocol Demo")
    if HAS_RICH:
        console.print("  AIS is to agent identity what OpenID Connect is to user identity.\n"
                      "  This demo walks through the complete protocol flow.\n")

    # ── Step 1: Discovery ─────────────────────────────────────────────────────
    step(1, "Discover Issuer   GET /.well-known/agent-issuer")

    resp = await client.get("/.well-known/agent-issuer")
    resp.raise_for_status()
    issuer_meta = resp.json()

    ok(f"Issuer:  {issuer_meta['issuer']}")
    ok(f"Spec:    {issuer_meta['spec_version']}")
    show_table([
        ("jwks_uri",                     issuer_meta["jwks_uri"]),
        ("agent_registration_endpoint",  issuer_meta["agent_registration_endpoint"]),
        ("agent_attestation_endpoint",   issuer_meta["agent_attestation_endpoint"]),
        ("supported_assertion_types",    str(issuer_meta["supported_assertion_types"])),
        ("supported_signing_alg_values", str(issuer_meta["supported_signing_alg_values"])),
        ("supported_framework_values",   str(issuer_meta["supported_framework_values"])),
    ], title="Discovery document")

    # ── Step 2: JWKS ──────────────────────────────────────────────────────────
    step(2, "Retrieve JWKS   GET /.well-known/jwks.json")

    # Registering an agent first ensures a key pair exists
    # (JWKS is empty until at least one org registers an agent)
    pre_reg = await client.post("/api/agents/register", json={
        "org_id": "demo-org",
        "team_id": "demo-team",
        "display_name": "JWKS Seed Agent",
        "framework": "custom",
        "environment": "development",
    }, headers={"x-acp-admin-token": "acp-demo-admin-token"})

    jwks_resp = await client.get("/.well-known/jwks.json")
    jwks_resp.raise_for_status()
    jwks = jwks_resp.json()

    if jwks["keys"]:
        key = jwks["keys"][0]
        ok(f"Published {len(jwks['keys'])} key(s) in JWKS")
        show_table([
            ("kty", key["kty"]),
            ("alg", key["alg"]),
            ("use", key["use"]),
            ("kid", key["kid"]),
            ("n",   key["n"][:48] + "..."),
        ], title="First JWK")
    else:
        info("JWKS empty — no agents registered yet for this org")

    # ── Step 3: Register agent ────────────────────────────────────────────────
    step(3, "Register Agent   POST /api/agents/register")

    reg_resp = await client.post("/api/agents/register", json={
        "org_id": "demo-org",
        "team_id": "payments-team",
        "display_name": "Payments Reconciliation Agent",
        "framework": "langgraph",
        "environment": "production",
        "tags": {"cost_center": "finance", "criticality": "high"},
    }, headers={"x-acp-admin-token": "acp-demo-admin-token"})
    reg_resp.raise_for_status()
    reg = reg_resp.json()

    agent = reg["agent"]
    token: str = reg["token"]

    ok(f"Agent registered:  {agent['agent_id']}")
    show_table([
        ("display_name", agent["display_name"]),
        ("framework",    agent["framework"]),
        ("environment",  agent["environment"]),
        ("status",       agent["status"]),
        ("org_id",       agent["org_id"]),
        ("team_id",      agent["team_id"]),
    ])

    # ── Step 4: Decode token offline ──────────────────────────────────────────
    step(4, "Decode agent+jwt Offline   (no network call)")

    jwt_header, jwt_payload = decode_jwt_parts(token)

    ok(f"Token type:  {jwt_header.get('typ')}")
    ok(f"Algorithm:   {jwt_header.get('alg')}")
    ok(f"Key ID:      {jwt_header.get('kid')}")
    info("Token header:")
    show_json(jwt_header)

    ok("Token payload (agent claims):")
    show_json(jwt_payload)

    info("Signature verification happens in Step 5 via the JWKS.")

    # ── Step 5: Attest ────────────────────────────────────────────────────────
    step(5, "Attestation Challenge-Response   POST /v1/attestations/challenge")

    challenge_resp = await client.post("/v1/attestations/challenge", json={
        "audience": f"{base_url}/gateway",
        "requested_claims": ["framework", "environment", "build_digest", "runtime_class"],
        "agent_id": agent["agent_id"],
    })
    challenge_resp.raise_for_status()
    challenge = challenge_resp.json()

    ok(f"Challenge issued:  {challenge['challenge_id']}")
    show_table([
        ("issuer",            challenge["issuer"]),
        ("audience",          challenge["audience"]),
        ("nonce",             challenge["nonce"]),
        ("expires_at",        challenge["expires_at"]),
        ("requested_claims",  str(challenge["requested_claims"])),
    ])

    if HAS_RICH:
        console.print("\n  [bold yellow][ 5b ][/bold yellow] [bold yellow]Submit Attestation Response   POST /v1/attestations[/bold yellow]")
    else:
        print("\n[5b] Submit Attestation Response   POST /v1/attestations")

    attest_resp = await client.post("/v1/attestations", json={
        "challenge_id": challenge["challenge_id"],
        "nonce":         challenge["nonce"],
        # The agent assertion is the JWT issued at registration
        "agent_assertion": token,
        "claims": {
            "framework":    agent["framework"],
            "environment":  agent["environment"],
            "runtime_class": "cloud_run",
            "build_digest":  "sha256:5b8e43d2c8f7f0ab32a9db38d4c1b14b7d0f6b2de3a8cd21f9308c4c65ad14f1",
        },
        "evidence": {
            "type": "workload_identity",
            "provider": "gcp",
        },
        "signature": "demo-attestation-envelope-signature",
    })
    attest_resp.raise_for_status()
    result = attest_resp.json()

    verified = result.get("jwt_verified", False)
    level    = result.get("attestation_level", "unknown")

    if verified:
        ok(f"JWT signature verified against JWKS  (attestation_level: {level})")
    else:
        info(f"Attestation level: {level}")
        if result.get("jwt_verification_note"):
            info(f"Note: {result['jwt_verification_note']}")

    show_table([
        ("verified",          str(result["verified"])),
        ("jwt_verified",      str(result.get("jwt_verified"))),
        ("attestation_level", result.get("attestation_level", "")),
        ("satisfied_claims",  str(result["satisfied_claims"])),
        ("missing_claims",    str(result["missing_claims"])),
        ("agent_id",          result.get("agent_id", "(not decoded)")),
        ("framework",         result.get("framework", "(not decoded)")),
        ("environment",       result.get("environment", "(not decoded)")),
    ], title="Attestation result")

    # ── Summary ───────────────────────────────────────────────────────────────
    if HAS_RICH:
        console.print()
        console.print(Panel(
            "[bold green]AIS protocol flow complete.[/bold green]\n\n"
            "  [dim]Discovery[/dim]   /.well-known/agent-issuer  →  issuer metadata\n"
            "  [dim]JWKS[/dim]        /.well-known/jwks.json     →  public keys for offline verification\n"
            "  [dim]Register[/dim]    /api/agents/register       →  agent+jwt (RS256, kid-bound)\n"
            "  [dim]Verify[/dim]      offline JWT decode          →  no issuer call required\n"
            "  [dim]Attest[/dim]      challenge-response          →  runtime claims + JWT verification\n\n"
            "  See [cyan]ais/SPEC.md[/cyan] for the full specification.",
            title="Done",
            border_style="green",
        ))
    else:
        print("\n=== AIS protocol flow complete ===")
        print("  See ais/SPEC.md for the full specification.")


# ── Entry point ───────────────────────────────────────────────────────────────

async def _run_with_transport(transport: httpx.AsyncBaseTransport, base_url: str) -> None:
    async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
        await run_demo(client, base_url)


async def _run_against_live(url: str) -> None:
    async with httpx.AsyncClient(base_url=url) as client:
        await run_demo(client, url)


def main() -> None:
    live_url: str | None = None
    args = sys.argv[1:]
    if "--url" in args:
        idx = args.index("--url")
        if idx + 1 < len(args):
            live_url = args[idx + 1]

    if live_url:
        # Point at a live ACP server
        if HAS_RICH:
            console.print(f"[dim]Connecting to live server: {live_url}[/dim]")
        asyncio.run(_run_against_live(live_url))
    else:
        # Self-contained: boot the ACP app in-process via ASGI transport
        try:
            from httpx import ASGITransport
            from acp.main import app
            from acp.database import create_all_tables
        except ImportError as exc:
            print(f"Cannot import ACP app: {exc}")
            print("Install dependencies first:  pip install -e .")
            sys.exit(1)

        async def _run() -> None:
            await create_all_tables()
            transport = ASGITransport(app=app)
            await _run_with_transport(transport, "http://localhost")

        asyncio.run(_run())


if __name__ == "__main__":
    main()
