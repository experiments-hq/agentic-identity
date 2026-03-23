# Agentic Identity (AIS)

**An open identity layer for autonomous AI agents.**
AIS gives agents a portable, discoverable, offline-verifiable identity model designed for real-world trust, policy, and interoperability.

## Why AIS exists

AI agents are becoming active participants in software systems: they call APIs, use tools, access internal systems, and take actions across organizational boundaries.

Today, most agents are represented as one of the following:
- API keys
- service accounts
- application clients
- user impersonations
- framework-specific opaque IDs

These approaches are often good enough for basic access, but they do not cleanly express **agent-native identity**, **portable trust**, or **runtime-aware verification**.

AIS is designed to address that gap.

## What AIS provides

AIS is an open specification and reference implementation for agent identity, including:

- **issuer discovery** for agent identity providers
- **signed agent assertions**
- **JWKS-based offline verification**
- **challenge-response attestation**
- **portable verification across runtimes and systems**
- **clear separation between identity and enterprise control-plane policy**

In practical terms, AIS helps answer questions like:

- What agent is making this request?
- Who issued this identity?
- Can I verify it offline?
- Can I trust its runtime posture?
- What policy should apply to it?

---

## Project structure

This repository contains two related but distinct layers:

### 1. AIS — the open specification
The specification defines the identity model, token format, metadata discovery, and attestation flow for autonomous agents.

See:
- [`spec/SPEC.md`](spec/SPEC.md)
- [`spec/ATTESTATION.md`](spec/ATTESTATION.md)
- [`docs/architecture.md`](docs/architecture.md)

### 2. ACP — the reference implementation / control plane
ACP is a reference implementation that issues and verifies agent identity and demonstrates how AIS can plug into enterprise policy and governance workflows.

See:
- [`acp/`](acp/)
- [`demo/`](demo/)
- [`examples/`](examples/)

---

## Who this is for

AIS is designed for:

- **AI platform teams** building agent infrastructure
- **security and IAM teams** who need strong identity and verification for agent workloads
- **API gateway and infrastructure teams** validating agent requests
- **framework and platform authors** who want interoperable agent trust
- **enterprise teams** that need auditable, policy-aware agent access

---

## What makes AIS different

AIS is built around a simple idea:

> Agents should be first-class principals, not awkward approximations of users or service accounts.

AIS is not trying to replace existing identity systems.
It is designed to complement them by introducing an identity model that is better suited to autonomous software actors.

Key properties:

- **offline-verifiable**
  Verifiers should not need a live call to a central control plane for every request.

- **portable**
  Agent identity should work across frameworks, runtimes, and organizational boundaries.

- **runtime-aware**
  Identity alone is not enough. AIS includes an attestation model for stronger trust decisions.

- **extensible**
  Governance, policy, approvals, and audit systems can be layered on top without making the identity layer proprietary.

---

## Quickstart

### Read the architecture
Start here if you want the conceptual model:

- [`docs/overview.md`](docs/overview.md)
- [`docs/problem.md`](docs/problem.md)
- [`docs/architecture.md`](docs/architecture.md)

### Read the spec
Start here if you want protocol details:

- [`spec/SPEC.md`](spec/SPEC.md)
- [`spec/ATTESTATION.md`](spec/ATTESTATION.md)

### Run the demo
Start here if you want to see the system end-to-end:

- [`demo/README.md`](demo/README.md)

### Use the SDK
Start here if you want to verify assertions in code:

- [`sdk/README.md`](sdk/README.md)

---

## Example flow

A typical AIS flow looks like this:

1. An agent receives identity from an issuer.
2. The issuer publishes metadata and signing keys.
3. The agent presents a signed assertion to a verifier.
4. The verifier discovers issuer metadata and validates the assertion offline.
5. If required, the verifier performs challenge-response attestation.
6. Local policy decides whether to allow the requested action.

This enables a verifier to make trust decisions without coupling every request to a centralized identity service.

---

## Core concepts

### Agent Issuer
A trusted authority that mints identity for autonomous agents.

### Agent Assertion
A signed identity document presented by an agent to another system.

### Verifier
A service, gateway, or application that validates the agent's identity and optionally requests attestation.

### Attestation
A challenge-response mechanism that helps verify runtime integrity or execution posture beyond static identity claims.

### Control Plane
An optional management layer that can handle policy, approvals, audit, observability, and operational governance.

---

## Use cases

AIS is especially useful for:

- **internal tool access**
  Agents accessing internal APIs or business systems with verifiable identity

- **API gateway enforcement**
  Gateways validating agent assertions before routing requests

- **cross-system trust**
  One platform verifying agents issued by another platform

- **audit and compliance**
  Creating clearer provenance around agent actions and delegated access

- **enterprise policy enforcement**
  Applying security and governance rules to autonomous agents as first-class actors

See [`docs/use-cases.md`](docs/use-cases.md) for more.

---

## AIS and MCP

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) and AIS address different problems in the agent stack.

**MCP handles data context.** It defines how agents discover and consume tools, resources, and structured data. MCP answers: *what can this agent access?*

**AIS handles principal identity.** It defines who the agent is, who issued that identity, and whether it can be verified. AIS answers: *who is making this request, and can I trust the claim?*

These are complementary. An agent can present an AIS assertion to identify itself, while using MCP to discover what tools are available. A gateway can verify the AIS assertion before routing MCP traffic. A policy system can enforce different rules based on the verified agent identity.

AIS does not compete with MCP. It sits at a different layer: identity and trust rather than capability discovery.

---

## Comparison

AIS is often compared to:

- OIDC
- OAuth client credentials
- service accounts
- SPIFFE / workload identity
- application JWT patterns

See [`docs/comparison.md`](docs/comparison.md) for where AIS fits and where it differs.

---

## Current status

AIS is currently in **draft stage**.

This means:
- the specification is still evolving
- field names and flows may change
- conformance guidance is incomplete
- ecosystem integrations are still early

If you are experimenting, building integrations, or evaluating design tradeoffs, this is a good time to engage.

If you are looking for a stable production standard, treat the current version as early.

See [`ROADMAP.md`](ROADMAP.md) for planned milestones.

---

## Design principles

AIS is guided by the following principles:

- agents are not users
- agent verification should be possible offline
- identity and governance should be separable
- trust decisions should be explainable and auditable
- the ecosystem benefits from open, interoperable standards

---

## Security

Because AIS is a security-sensitive system, responsible disclosure matters.

Please see [`SECURITY.md`](SECURITY.md) before reporting vulnerabilities.

You should also review:
- [`docs/threat-model.md`](docs/threat-model.md)
- [`spec/ATTESTATION.md`](spec/ATTESTATION.md)

---

## Contributing

We welcome feedback from:
- identity practitioners
- security engineers
- AI platform teams
- framework authors
- API gateway vendors
- researchers working on trustworthy agent systems

Please see [`CONTRIBUTING.md`](CONTRIBUTING.md).

Good first contribution areas:
- verifier integrations
- gateway examples
- framework adapters
- conformance tests
- threat-model review
- protocol feedback

---

## Roadmap

Near-term priorities:
- tighten the draft specification
- improve conformance guidance
- expand verifier and issuer examples
- publish clearer framework and gateway integrations
- mature attestation semantics
- gather ecosystem feedback

See [`ROADMAP.md`](ROADMAP.md) for details.

---

## FAQ

### Is AIS trying to replace OIDC or SPIFFE?
No. AIS is intended to address the identity needs of autonomous agents specifically, while remaining compatible with broader identity ecosystems where appropriate.

### Is ACP required to use AIS?
No. ACP is a reference implementation and control-plane example. AIS is intended to be usable independently of any single vendor or product.

### Why not just use service accounts?
Service accounts can authenticate software, but they do not always capture the semantics, trust posture, portability, or governance requirements of autonomous agents.

### Why offline verification?
Offline verification reduces latency, dependency on centralized infrastructure, and platform lock-in for every trust decision.

---

## Repository guide

- `docs/` — conceptual documentation, architecture, comparisons, and use cases
- `spec/` — protocol and attestation specification
- `acp/` — reference implementation / control plane
- `sdk/` — verifier and issuer SDKs
- `examples/` — runnable integration examples
- `demo/` — end-to-end demo assets

---

## Get involved

We are especially interested in collaboration with:
- agent framework authors
- security and IAM teams
- API gateway and infrastructure vendors
- teams experimenting with real-world agent trust and governance

If this space is relevant to your work, open an issue or start a discussion.
