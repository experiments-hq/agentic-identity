# Agent Identity Specification

Version `0.1-draft`

The Agent Identity Specification (AIS) defines an interoperable way to identify, issue credentials to, verify, and attest autonomous AI agents.

AIS is designed to be for agent identity what OpenID Connect is for user identity:
- issuer-based trust
- discovery metadata
- JWKS-published verification keys
- signed tokens with portable claims
- an attestation protocol for runtime properties

## Scope

AIS standardizes:
- the canonical `AgentIdentity` document
- the `agent_assertion` credential format
- issuer discovery metadata
- JWKS key publication
- a challenge-response attestation flow

AIS does not standardize:
- orchestration frameworks
- model inference APIs
- policy engines
- observability vendors

## Design Principles

1. Framework-neutral
Agents built with LangGraph, CrewAI, AutoGen, custom runtimes, and future frameworks should all fit the same identity model.

2. Cloud-neutral
Verification should not require a call back into a specific vendor control plane on every request.

3. Verifiable offline
Consumers should be able to validate agent credentials from discovery metadata and JWKS alone.

4. Explicit non-human identity
Agents are not users. Agent principals must not inherit user permissions implicitly.

5. Attestable runtime posture
An agent should be able to prove relevant runtime facts such as framework, environment, build provenance, or execution class.

## Document Set

- [SPEC.md](c:/Users/nenye/acp/ais/SPEC.md): normative core specification
- [ATTESTATION.md](c:/Users/nenye/acp/ais/ATTESTATION.md): challenge-response attestation protocol
- [schema/agent-identity.schema.json](c:/Users/nenye/acp/ais/schema/agent-identity.schema.json): canonical identity schema
- [examples/issuer-metadata.json](c:/Users/nenye/acp/ais/examples/issuer-metadata.json): discovery metadata example
- [examples/jwks.json](c:/Users/nenye/acp/ais/examples/jwks.json): JWKS example
- [examples/agent-assertion.payload.json](c:/Users/nenye/acp/ais/examples/agent-assertion.payload.json): token payload example
- [examples/attestation-request.json](c:/Users/nenye/acp/ais/examples/attestation-request.json): attestation challenge example
- [examples/attestation-response.json](c:/Users/nenye/acp/ais/examples/attestation-response.json): attestation response example

## OpenID Connect Analogy

AIS is intentionally shaped like a machine-oriented cousin of OpenID Connect:

| OpenID Connect | AIS |
| --- | --- |
| OpenID Provider | Agent Issuer |
| ID Token | Agent Assertion |
| Discovery Metadata | Agent Issuer Metadata |
| JWKS URI | Agent JWKS URI |
| User Claims | Agent Claims |
| Authentication Context | Attestation Context |

The key difference is that AIS is optimized for non-human autonomous systems rather than end-user login.
