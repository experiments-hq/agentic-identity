"""Integration tests for ais-verify SDK.

Requires the ACP server running on port 8000:
    cd acp && uvicorn acp.main:app --reload --port 8000
"""
import asyncio
import sys
import os

# Windows encoding fix
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

BASE = "http://127.0.0.1:8000"
ADMIN_TOKEN = "acp-demo-admin-token"
DEMO_ORG_ID = "org-live-demo"
DEMO_TEAM_ID = "team-live-demo"

PASS = "  ✓ PASS"
FAIL = "  ✗ FAIL"

errors = []


def ok(label: str, detail: str = "") -> None:
    print(f"{PASS}  {label}" + (f" — {detail}" if detail else ""))


def fail(label: str, detail: str = "") -> None:
    msg = f"{FAIL}  {label}" + (f" — {detail}" if detail else "")
    print(msg)
    errors.append(msg)


# ---------------------------------------------------------------------------
# Async setup: register agent + get a real signed agent+jwt from ACP
# ---------------------------------------------------------------------------

async def get_test_token() -> tuple[str, dict, str]:
    """Register a fresh agent and return (jwt, jwks, agent_id)."""
    headers = {"x-acp-admin-token": ADMIN_TOKEN, "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15.0) as c:
        # Register agent — JWT is returned directly in the registration response
        r = await c.post("/api/agents/register", json={
            "org_id": DEMO_ORG_ID,
            "team_id": DEMO_TEAM_ID,
            "framework": "langgraph",
            "environment": "staging",
            "display_name": "SDK test agent",
            "created_by": "sdk-test",
        })
        r.raise_for_status()
        reg = r.json()
        agent_id = reg["agent"]["agent_id"]
        jwt = reg["token"]

        # Get JWKS (public endpoint, no auth required)
        r = await c.get("/.well-known/jwks.json")
        r.raise_for_status()
        jwks = r.json()

    return jwt, jwks, agent_id


# ---------------------------------------------------------------------------
# Async tests (run inside a single event loop)
# ---------------------------------------------------------------------------

async def run_async_tests(jwt: str, jwks: dict) -> None:
    from ais_verify import (
        AgentVerifier,
        AgentClaims,
        verify_agent_jwt,
        InvalidSignatureError,
        AISVerificationError,
    )

    print("\n── Async tests ──────────────────────────────────────────────────")

    # Test 1: AgentVerifier with live issuer discovery
    print("\nTest 1: AgentVerifier — issuer discovery")
    try:
        verifier = AgentVerifier(issuer=BASE)
        claims = await verifier.verify(jwt)
        assert isinstance(claims, AgentClaims), "claims is not AgentClaims"
        assert claims.framework == "langgraph", f"framework={claims.framework!r}"
        assert claims.environment == "staging", f"env={claims.environment!r}"
        ok("AgentVerifier(issuer=...) → AgentClaims", f"agent_id={claims.agent_id[:8]}…")
    except Exception as e:
        fail("AgentVerifier issuer discovery", str(e))

    # Test 2: one-shot verify_agent_jwt helper
    print("\nTest 2: verify_agent_jwt() one-shot")
    try:
        claims2 = await verify_agent_jwt(jwt, issuer=BASE)
        assert claims2.agent_id == claims.agent_id, "agent_id mismatch"
        ok("verify_agent_jwt(jwt, issuer=...) returned same claims")
    except Exception as e:
        fail("verify_agent_jwt one-shot", str(e))

    # Test 3: offline verification with explicit JWKS (no network calls)
    print("\nTest 3: AgentVerifier — offline with explicit JWKS")
    try:
        verifier_offline = AgentVerifier(jwks=jwks)
        claims3 = await verifier_offline.verify(jwt)
        assert claims3.agent_id == claims.agent_id, "agent_id mismatch"
        ok("AgentVerifier(jwks=...) offline — no discovery needed")
    except Exception as e:
        fail("AgentVerifier offline JWKS", str(e))

    # Test 5: required_environment enforcement
    print("\nTest 5: Policy enforcement — required_environment mismatch")
    try:
        verifier_offline2 = AgentVerifier(jwks=jwks)
        await verifier_offline2.verify(jwt, required_environment="production")
        fail("required_environment=production (token is staging)", "should have raised")
    except AISVerificationError as e:
        ok("Correctly rejected: AISVerificationError", str(e)[:60])
    except Exception as e:
        fail("required_environment enforcement", f"unexpected {type(e).__name__}: {e}")

    # Test 6: tampered signature → InvalidSignatureError
    print("\nTest 6: Tampered signature rejection")
    try:
        parts = jwt.split(".")
        # Flip the last 4 chars of the signature
        bad_sig = parts[2][:-4] + ("XXXX" if parts[2][-4:] != "XXXX" else "YYYY")
        bad_token = ".".join(parts[:2] + [bad_sig])
        verifier_offline3 = AgentVerifier(jwks=jwks)
        await verifier_offline3.verify(bad_token)
        fail("Tampered token", "should have raised InvalidSignatureError")
    except InvalidSignatureError as e:
        ok("Correctly raised InvalidSignatureError")
    except Exception as e:
        fail("Tampered signature", f"unexpected {type(e).__name__}: {e}")

    # Test 7: missing required claim (crafted payload — use allow_expired trick)
    print("\nTest 7: Constructor validation — neither issuer nor jwks")
    try:
        AgentVerifier()  # should raise ValueError
        fail("AgentVerifier() with no args", "should have raised ValueError")
    except ValueError as e:
        ok("Correctly raised ValueError", str(e)[:60])
    except Exception as e:
        fail("AgentVerifier() no args", f"unexpected {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Sync test (must run OUTSIDE any event loop)
# ---------------------------------------------------------------------------

def run_sync_test(jwt: str, jwks: dict) -> None:
    from ais_verify import verify_agent_jwt_sync, AgentClaims

    print("\n── Sync test ────────────────────────────────────────────────────")
    print("\nTest 4: verify_agent_jwt_sync() — sync wrapper")
    try:
        claims = verify_agent_jwt_sync(jwt, jwks=jwks)
        assert isinstance(claims, AgentClaims), "claims is not AgentClaims"
        assert claims.framework == "langgraph", f"framework={claims.framework!r}"
        ok("verify_agent_jwt_sync(jwt, jwks=...) returned AgentClaims",
           f"agent_id={claims.agent_id[:8]}…")
    except Exception as e:
        msg = f"verify_agent_jwt_sync"
        print(f"{FAIL}  {msg} — {e}")
        errors.append(f"{FAIL}  {msg} — {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("ais-verify SDK — integration test suite")
    print(f"Target ACP server: {BASE}\n")

    # Step 1: Register agent and get a real signed JWT (async setup)
    print("Setting up: registering test agent and fetching assertion…")
    try:
        jwt, jwks, agent_id = asyncio.run(get_test_token())
        print(f"  Got JWT ({len(jwt)} chars), JWKS ({len(jwks.get('keys', []))} keys)\n")
    except Exception as e:
        print(f"\nFATAL: Could not connect to ACP server at {BASE}: {e}")
        print("Make sure the server is running:  uvicorn acp.main:app --reload --port 8000")
        sys.exit(1)

    # Step 2: Sync test (must happen before any asyncio.run in this thread)
    run_sync_test(jwt, jwks)

    # Step 3: Async tests
    asyncio.run(run_async_tests(jwt, jwks))

    # Summary
    print("\n" + "─" * 60)
    total = 7
    failed = len(errors)
    passed = total - failed
    print(f"Results: {passed}/{total} passed")
    if errors:
        print("\nFailures:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("All tests passed.")


if __name__ == "__main__":
    main()
