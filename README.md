# Agent Identity Specification (AIS)

AIS is an open protocol for agent identity — the same class of standard OpenID Connect established for user identity, adapted for autonomous AI agents.

```
OpenID Connect  →  users and OAuth clients
AIS             →  autonomous AI agents
```

An AIS-conformant issuer publishes:
- **issuer discovery** at `/.well-known/agent-issuer`
- **JWKS** at `/.well-known/jwks.json` for offline-verifiable credentials
- **signed agent assertions** (`agent+jwt`, RS256) carrying portable identity claims
- **a challenge-response attestation protocol** for proving runtime properties

Agents built with LangGraph, CrewAI, AutoGen, or any custom runtime fit the same identity model. Verification never requires a live issuer callback — only the published JWKS.

---

## Quick Demo

```bash
git clone https://github.com/experiments-hq/agentic-identity.git
cd agentic-identity
pip install -e .
python demo.py
```

The demo walks through the full AIS protocol flow in-process, no server setup required:

```
[ 1 ]  Discover issuer      GET /.well-known/agent-issuer
[ 2 ]  Retrieve JWKS        GET /.well-known/jwks.json
[ 3 ]  Register agent       POST /api/agents/register  →  agent+jwt
[ 4 ]  Decode token offline  no network call required
[ 5 ]  Attest               challenge-response, JWT signature verified against JWKS
```

---

## Protocol Overview

### 1. Issuer Discovery

```http
GET /.well-known/agent-issuer
```

```json
{
  "issuer": "https://acp.example.com",
  "spec_version": "0.1-draft",
  "jwks_uri": "https://acp.example.com/.well-known/jwks.json",
  "agent_registration_endpoint": "https://acp.example.com/v1/agents",
  "agent_attestation_endpoint": "https://acp.example.com/v1/attestations",
  "supported_assertion_types": ["agent+jwt"],
  "supported_signing_alg_values": ["RS256"]
}
```

### 2. Agent Registration

```http
POST /api/agents/register
{
  "org_id": "org-acme",
  "team_id": "team-finance",
  "display_name": "Payments Reconciliation Agent",
  "framework": "langgraph",
  "environment": "production"
}
```

Returns a signed `agent+jwt`:

```
eyJhbGciOiJSUzI1NiIsInR5cCI6ImFnZW50K2p3dCIsImtpZCI6IjJmOWFlZjczIn0
.eyJpc3MiOiJodHRwczovL2FjcC5leGFtcGxlLmNvbSIsInN1YiI6IjVmOGQ5ZjMyI...
.RSA-SHA256-signature
```

### 3. Offline Verification

Any verifier can validate the assertion without calling the issuer:

1. Fetch `/.well-known/agent-issuer` → resolve `jwks_uri`
2. Fetch JWKS → select key matching `kid`
3. Verify RS256 signature
4. Check `exp`, required claims, local policy

### 4. Attestation

```http
POST /v1/attestations/challenge
{ "audience": "https://gateway.example.com", "requested_claims": ["framework", "environment"] }

→ { "challenge_id": "...", "nonce": "...", "expires_at": "..." }

POST /v1/attestations
{ "challenge_id": "...", "nonce": "...", "agent_assertion": "<jwt>", "claims": {...}, "evidence": {...} }

→ { "verified": true, "jwt_verified": true, "attestation_level": "assertion_verified", ... }
```

---

## OIDC Analogy

| OpenID Connect | AIS |
|---|---|
| OpenID Provider | Agent Issuer |
| ID Token | Agent Assertion (`agent+jwt`) |
| Discovery Metadata | Agent Issuer Metadata |
| JWKS URI | Agent JWKS URI |
| User Claims | Agent Claims |
| Authentication Context | Attestation Context |

---

## Specification

The specification lives in [`ais/`](./ais/):

- [`ais/SPEC.md`](./ais/SPEC.md) — normative core specification
- [`ais/ATTESTATION.md`](./ais/ATTESTATION.md) — challenge-response attestation protocol
- [`ais/CONFORMANCE.md`](./ais/CONFORMANCE.md) — required vs. optional for implementers
- [`ais/schema/agent-identity.schema.json`](./ais/schema/agent-identity.schema.json) — canonical identity schema
- [`ais/examples/`](./ais/examples/) — example JSON documents

---

## Reference Implementation

The [`acp/`](./acp/) directory contains the **Agent Control Plane** — a full AIS reference implementation built with FastAPI and SQLite.

It implements all AIS-required endpoints and adds seven governance primitives on top:

| Primitive | Description |
|---|---|
| **Identity** | RSA JWT issuance, rotation, revocation, JWKS, discovery |
| **Policy** | YAML DSL policy engine — allow / deny / require_approval |
| **Observability** | Distributed trace + span recording, cost attribution |
| **Approvals** | Human-in-the-loop gates for high-risk agent actions |
| **Budget** | Token and cost limits with rolling/calendar windows |
| **Replay** | Session capture and deterministic incident replay |
| **Audit** | SHA-256 hash-chain tamper-evident log, EU AI Act + SOC 2 reports |

### Running the ACP Server

```bash
pip install -e .
acp serve
# or
python -m acp.main
```

```
http://localhost:8000/docs           # OpenAPI explorer
http://localhost:8000/console        # Governance console
http://localhost:8000/.well-known/agent-issuer
http://localhost:8000/.well-known/jwks.json
```

---

## Verifier SDK

**`ais-verify`** — standalone Python SDK for offline `agent+jwt` verification. No ACP server required, no governance stack, just the token and a JWKS.

```bash
pip install ais-verify
```

```python
from ais_verify import AgentVerifier

# Online — resolves JWKS from issuer discovery
verifier = AgentVerifier(issuer="https://acp.example.com")
claims = await verifier.verify(token)
print(claims.agent_id, claims.framework, claims.environment)

# Offline — pass JWKS dict directly, no network calls
verifier = AgentVerifier(jwks={"keys": [...]})
claims = await verifier.verify(token)

# Policy enforcement
claims = await verifier.verify(token, required_environment="production")
```

```
OpenID Connect  →  PyJWT / python-jose  →  verify ID tokens
AIS             →  ais-verify           →  verify agent+jwt tokens
```

Source: [`sdk/`](./sdk/) — only deps: `cryptography` + `httpx`

---

## Status

`0.1-draft` — the specification and reference implementation are in active development. The protocol shape is stable; field names and endpoint paths may evolve before a 1.0 release.

---

## Design Rationale

The reasoning behind key decisions — why not OIDC directly, why RS256, why offline-first verification, why a separate attestation protocol, how AIS relates to SPIFFE and W3C VCs — is documented in [`RATIONALE.md`](./RATIONALE.md).

---

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for how to report issues, propose spec changes, and run the development environment.

Version history is in [`CHANGELOG.md`](./CHANGELOG.md).

Feedback, issues, and pull requests welcome. Particularly valuable input would come from agent framework authors, gateway vendors, model providers, workload identity practitioners, and identity standards groups.
