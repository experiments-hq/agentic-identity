[![CI](https://github.com/experiments-hq/agentic-identity/actions/workflows/ci.yml/badge.svg)](https://github.com/experiments-hq/agentic-identity/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

# AIS — Identity Infrastructure for AI Agents

**The open identity layer that lets any system verify which agent is making a request, who issued that identity, and whether to trust it.**

---

## The Problem

AI agents are calling APIs, executing tools, and taking actions across organizational boundaries — but most have no verifiable identity. They authenticate with shared API keys, borrowed user credentials, or framework-specific opaque IDs that no downstream system can independently verify.

The numbers tell the story:

- **88%** of organizations reported a confirmed or suspected AI agent security incident in the last year ([Gravitee 2026](https://www.gravitee.io/state-of-ai-agent-security))
- **45.6%** rely on shared API keys for agent-to-agent authentication
- **Only 21.9%** treat AI agents as independent identity-bearing entities
- **OWASP LLM06** (Excessive Agency) identifies this as a top-10 LLM risk
- A real-world financial services breach — prompt injection via a shipping address field led to unauthorized invoicing tool access and data exfiltration ([CyberArk 2026](https://www.cyberark.com/resources/blog/ai-agents-and-identity-risks-how-security-will-shift-in-2026))

Every enterprise deploying agents is reinventing identity from scratch. Gateways cannot distinguish agent calls from generic service traffic. Policy engines lack portable claims. Post-incident attribution is guesswork.

AIS fixes this.

---

## Verify an Agent in 3 Lines

```python
from ais_verify import AgentVerifier

verifier = AgentVerifier(issuer="https://acp.example.com")
claims = await verifier.verify(token)

print(claims.agent_id)     # "5f8d9f32-..."
print(claims.org_id)       # "org-acme"
print(claims.framework)    # "langgraph"
print(claims.environment)  # "production"
```

Offline verification. No issuer callback required. Works at any gateway, API, or service boundary.

---

## Quickstart

### Docker (fastest)

```bash
docker build -t acp . && docker run -p 8000:8000 acp
```

Open `http://localhost:8000/console/` for the governance console. API docs at `http://localhost:8000/docs`.

### Local install

```bash
pip install -e ".[dev]"
acp demo-seed
acp serve
```

### Run the SDK standalone

```bash
cd sdk && pip install -e .
```

```python
from ais_verify import verify_agent_jwt

claims = await verify_agent_jwt(token, issuer="https://acp.example.com")
```

---

## What AIS Provides

**Identity primitives:**
- Issuer discovery via `/.well-known/agent-issuer`
- Signed agent assertions (`agent+jwt`) with agent-native claims
- JWKS-based offline verification — no per-request issuer dependency
- Challenge-response runtime attestation
- Portable verification across frameworks, runtimes, and organizational boundaries

**Control plane primitives (reference implementation):**
- Identity registry and credential lifecycle
- YAML-based policy engine (allow / deny / require_approval)
- Human-in-the-loop approval workflows
- Per-agent budget enforcement
- Tamper-evident audit log with SHA-256 hash chain
- Distributed tracing and observability
- Incident replay

---

## Trust Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent Issuer                         │
│  /.well-known/agent-issuer   /.well-known/jwks.json         │
│  /api/agents/register        /v1/attestations               │
└───────────────────────┬─────────────────────────────────────┘
                        │
              (1) register + receive agent+jwt
                        │
                   ┌────▼─────┐
                   │  Agent   │
                   └────┬─────┘
                        │
              (2) present agent+jwt to verifier
                        │
                   ┌────▼──────────────────────────────────┐
                   │  Verifier (gateway / API / service)   │
                   │                                       │
                   │  (3) validate JWT offline via JWKS    │
                   │  (4) optionally request attestation   │
                   │  (5) enforce local policy             │
                   └───────────────────────────────────────┘
```

---

## Why AIS

| Approach | Principal type | Offline verification | Agent-specific claims | Attestation | Portability |
|---|---|---|---|---|---|
| OIDC | Human user | Yes | No | No | High |
| OAuth client credentials | Software client | Partial | No | No | Medium |
| Service accounts | Workload / service | Depends on platform | No | No | Low |
| SPIFFE / SVID | Workload | Yes (X.509) | No | No | Medium |
| W3C VCs | General (human focus) | Yes | Custom | Partial | High |
| Application JWTs | Ad hoc | Depends | Custom | No | Low |
| **AIS** | **Autonomous agent** | **Yes** | **Yes** | **Yes** | **High** |

See [`docs/comparison.md`](docs/comparison.md) for detailed analysis.

---

## AIS and MCP

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) defines how agents discover and consume tools, resources, and structured data — *what can this agent access?*

AIS defines who the agent is, who issued that identity, and whether it can be verified — *who is making this request, and can I trust the claim?*

These are complementary layers. An agent presents an AIS assertion to identify itself while using MCP to discover available tools. A gateway verifies the AIS assertion before routing MCP traffic. A policy engine enforces rules based on the verified agent identity.

---

## Enterprise and Cloud

**ACP Cloud** (coming soon) — hosted agent identity infrastructure with:

- Managed issuer and credential lifecycle
- Enterprise SSO integration (SAML, OIDC federation)
- Multi-tenant organization and team management
- Compliance audit trail and reporting
- Framework SDK marketplace and gateway plugins

Contact: **experiments-hq@outlook.com**

---

## For Implementers

### Specification

- [`spec/SPEC.md`](spec/SPEC.md) — token format, claims, discovery, verification
- [`spec/ATTESTATION.md`](spec/ATTESTATION.md) — challenge-response attestation protocol
- [`spec/CONFORMANCE.md`](spec/CONFORMANCE.md) — RFC 2119 implementer checklist

### Core concepts

- **Agent Issuer** — trusted authority that mints agent identity and publishes signing keys
- **Agent Assertion** (`agent+jwt`) — signed credential presented by an agent to any verifier
- **Verifier** — gateway, API, or service that validates identity offline via JWKS
- **Attestation** — challenge-response protocol for runtime integrity beyond static claims
- **Control Plane** — optional governance layer for policy, approvals, audit, and observability

### Repository guide

| Directory | Contents |
|---|---|
| `spec/` | Normative specification and conformance requirements |
| `sdk/` | `ais-verify` — standalone verifier SDK |
| `acp/` | Reference implementation / control plane |
| `docs/` | Architecture, comparisons, threat model, use cases |
| `examples/` | Gateway enforcement and integration examples |
| `demo/` | End-to-end protocol demo |
| `tests/` | Test suite |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). High-impact areas: verifier integrations, gateway examples, framework adapters, conformance tests, threat model review.

## Security

AIS is a security-sensitive protocol. See [`SECURITY.md`](SECURITY.md) and [`docs/threat-model.md`](docs/threat-model.md) for responsible disclosure and protocol-level threat analysis.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for current milestones and what's next.

---

## FAQ

**Is AIS trying to replace OIDC or SPIFFE?**
No. AIS uses OIDC's trust architecture (issuer discovery, JWKS, offline verification) and complements SPIFFE's workload identity. It adds what neither provides: an agent-native assertion type with claims designed for autonomous software principals.

**Is ACP required to use AIS?**
No. ACP is one reference implementation. Any system that implements the AIS spec endpoints can issue and verify agent identity. The spec and the product are separate.

**Why not just use service accounts?**
Service accounts authenticate workloads, not agents. They do not carry agent-specific claims (framework, environment, team, attestation level), are not portable across platforms, and provide no runtime attestation model.
