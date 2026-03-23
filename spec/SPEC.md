# Agent Identity Specification

Version: `0.1-draft`

## 1. Overview

AIS defines how an autonomous agent becomes a first-class security principal.

An AIS-conformant deployment publishes:
- an issuer identifier
- issuer metadata
- a JWKS document
- signed agent assertions
- an attestation endpoint or equivalent flow

## 2. Terminology

`Agent`
A non-human autonomous software system that reasons, invokes tools or APIs, and takes actions with limited human supervision.

`Agent Issuer`
A trusted authority that registers agents, issues credentials, rotates keys, and publishes verification metadata.

`Agent Assertion`
A signed JWT conveying the identity and posture of an agent.

`Attestation`
A cryptographic proof produced by an agent instance in response to an issuer or verifier challenge.

## 3. AgentIdentity Model

The canonical identity record contains:
- `agent_id`: globally unique immutable identifier
- `org_id`: owning organization
- `team_id`: owning team
- `display_name`: human-readable label
- `framework`: declared execution framework
- `environment`: development, staging, or production
- `status`: active, suspended, or revoked
- `created_at`
- `last_seen_at`
- `tags`

The normative JSON Schema is in [schema/agent-identity.schema.json](./schema/agent-identity.schema.json).

## 4. Discovery

An AIS issuer should publish metadata at:

`/.well-known/agent-issuer`

The metadata document should include:
- `issuer`
- `jwks_uri`
- `agent_registration_endpoint`
- `agent_attestation_endpoint`
- `supported_signing_alg_values`
- `supported_assertion_types`
- `supported_framework_values`
- `supported_environment_values`
- `spec_version`

Example: [examples/issuer-metadata.json](./examples/issuer-metadata.json)

## 5. Agent Assertions

AIS agent assertions are JWTs signed by the issuer.

### 5.1 Header

Required header parameters:
- `alg`
- `typ`
- `kid`

Recommended:
- `typ: agent+jwt`

### 5.2 Claims

Required claims:
- `iss`: issuer identifier
- `sub`: stable `agent_id`
- `aud`: intended verifier or resource audience
- `iat`
- `exp`
- `jti`
- `agent_id`
- `org_id`
- `team_id`
- `framework`
- `environment`

Optional claims:
- `display_name`
- `tags`
- `attestation_level`
- `build_digest`
- `runtime_class`

Example payload: [examples/agent-assertion.payload.json](./examples/agent-assertion.payload.json)

## 6. Verification

A verifier validates an AIS assertion by:
1. resolving issuer metadata
2. retrieving the issuer JWKS
3. selecting the key matching `kid`
4. verifying signature and expiry
5. validating required claims
6. enforcing local policy on framework, environment, audience, or attestation level

Verification should not require a synchronous call to the issuer beyond metadata and JWKS retrieval.

## 7. Revocation and Rotation

Issuers should support:
- proactive key rotation
- assertion expiry
- explicit agent suspension or revocation
- overlap windows during rotation

AIS does not require a global online introspection endpoint, but issuers may expose one.

## 8. Attestation

AIS attestation is a challenge-response protocol that binds runtime facts to an agent assertion.

Normative flow details are defined in [ATTESTATION.md](./ATTESTATION.md).

## 9. Security Considerations

- Agent assertions should be short-lived.
- Private signing keys must remain under issuer control.
- Agent credentials must not inherit user permissions implicitly.
- Attestation claims should be treated as scoped statements, not universal trust.
- Offline verification should be paired with local policy enforcement.

## 10. Interoperability Goal

The purpose of AIS is to let different control planes, frameworks, gateways, and enterprise systems agree on what an agent is and how its identity is verified.

That is the same class of interoperability goal OpenID Connect achieved for user identity, adapted for autonomous machine actors.
