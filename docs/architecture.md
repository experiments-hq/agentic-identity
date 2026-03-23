# Architecture

This document describes the components of an AIS deployment and how they interact.

---

## Components

### Agent Issuer

The issuer is the trusted authority responsible for:
- Registering agents and maintaining the identity registry
- Generating RSA key pairs per organization
- Signing agent assertions (`agent+jwt` tokens)
- Publishing issuer metadata at `/.well-known/agent-issuer`
- Publishing JWKS at `/.well-known/jwks.json`
- Supporting credential rotation and revocation

An issuer can be a standalone service, embedded in a control plane, or implemented by a framework. The ACP reference implementation (`acp/`) is one example of an issuer.

### Agent

An agent is a non-human autonomous software system. In the AIS model, an agent:
- Obtains its identity credential from an issuer at registration time
- Presents a signed `agent+jwt` assertion to verifiers when making requests
- Optionally participates in attestation flows to prove runtime posture

Agents do not need to know about JWKS or key material — they only need to present their credential.

### Verifier

A verifier is any service, gateway, or system that needs to validate agent identity. A verifier:
- Discovers issuer metadata from `/.well-known/agent-issuer`
- Fetches JWKS from the issuer (cacheable, no per-request dependency)
- Validates the agent's JWT signature, expiry, and required claims
- Optionally performs challenge-response attestation for higher-assurance decisions
- Enforces local policy based on the verified claims

Verification is designed to be offline — once JWKS is cached, no live issuer call is required.

### Control Plane (optional)

A control plane is an optional management layer that sits above the issuer. The ACP reference implementation demonstrates one possible control plane, which includes:
- Policy engine (YAML DSL, per-org rules)
- Human approval workflows
- Budget enforcement
- Observability and tracing
- Incident replay
- Audit log with hash-chain integrity

The control plane is not part of the AIS specification — it is a governance layer that builds on top of agent identity.

---

## Trust flow

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

## Key design decisions

### Offline verification
JWKS is fetched and cached by verifiers. Individual requests do not require a live call to the issuer. This is the same model OIDC uses for ID token verification — the issuer publishes keys, verifiers cache them.

### Separation of identity and governance
The AIS spec defines identity and verification. Policy, approvals, and audit are not part of the spec — they are the job of the control plane. This separation means AIS can be adopted by teams that already have policy infrastructure.

### agent+jwt as assertion type
Using `typ: agent+jwt` in the JWT header makes assertions self-describing. A verifier that encounters an `agent+jwt` can immediately identify its type without out-of-band context.

### RS256 as the default algorithm
RS256 is used across all major JWT libraries and identity platforms. This maximizes verifier compatibility for a new standard. Ed25519 is planned as a future option.

---

## Relationship to the spec

This document describes the conceptual architecture. For normative protocol details, see:
- [`spec/SPEC.md`](../spec/SPEC.md) — token format, claims, discovery, verification
- [`spec/ATTESTATION.md`](../spec/ATTESTATION.md) — challenge-response attestation protocol
- [`spec/CONFORMANCE.md`](../spec/CONFORMANCE.md) — implementer conformance requirements
