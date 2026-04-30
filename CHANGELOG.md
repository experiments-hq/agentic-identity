# Changelog

All notable changes to AIS and the ACP reference implementation are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). AIS uses [Semantic Versioning](https://semver.org/) for specification versions.

---

## [Unreleased]

---

## [0.1-draft] — 2025

Initial public draft of the Agent Identity Specification.

### Specification

**Added**

- `spec/SPEC.md` — normative core specification defining the AgentIdentity model, issuer discovery, agent assertions, verification, revocation, and attestation
- `spec/ATTESTATION.md` — challenge-response attestation protocol with nonce binding and JWKS-backed JWT verification
- `spec/CONFORMANCE.md` — implementer checklist with RFC 2119 MUST/SHOULD/MAY requirements across 9 conformance areas
- `spec/schema/agent-identity.schema.json` — canonical JSON Schema for the AgentIdentity document
- `spec/examples/` — example JSON documents: issuer metadata, JWKS, agent assertion payload, attestation request/response
- `docs/problem.md` — design rationale covering the identity gap problem, OIDC relationship, key design decisions, and non-goals

**Spec decisions**

- `agent+jwt` as the JWT `typ` value for agent assertions
- `/.well-known/agent-issuer` as the issuer discovery endpoint path
- RS256 as the required minimum signing algorithm; stronger algorithms advertised via `supported_signing_alg_values`
- Offline verification as a hard requirement — synchronous issuer callbacks must not be required for baseline verification
- Two-step attestation: `POST .../challenge` → `POST ...` with nonce binding

### Reference Implementation (ACP)

**Added**

- FastAPI server implementing all AIS-required endpoints plus seven governance primitives: Identity, Policy, Observability, Approvals, Budget, Replay, Audit
- RSA JWT issuance with key rotation, JWKS publication, revocation
- YAML-based policy DSL with allow / deny / require_approval actions
- Tamper-evident audit log with SHA-256 hash chain
- Interactive governance console at `/console`
- Admin CLI (`acp serve`, `acp agents list`, `acp audit export`)
- `demo.py` — self-contained protocol walkthrough (no server required; also works against a live ACP instance)

### SDK (`ais-verify`)

**Added**

- `AgentVerifier` class — offline and online `agent+jwt` verification
- `verify_agent_jwt` one-shot async helper
- `verify_agent_jwt_sync` synchronous variant
- Policy enforcement: `required_environment`, `required_framework`, `required_audience`
- JWKS caching with configurable TTL
- Typed `AgentClaims` return value
- Error types: `InvalidSignatureError`, `TokenExpiredError`, `MissingClaimError`, `IssuerDiscoveryError`

---

[Unreleased]: https://github.com/experiments-hq/agentic-identity/compare/v0.1-draft...HEAD
[0.1-draft]: https://github.com/experiments-hq/agentic-identity/releases/tag/v0.1-draft
