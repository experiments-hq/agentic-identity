# AIS Conformance Requirements

Version: `0.1-draft`

This document describes what an AIS-conformant issuer must, should, and may implement.

The key words "MUST", "SHOULD", and "MAY" follow [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## 1. Issuer Discovery

### REQUIRED

- The issuer MUST serve an issuer metadata document at `/.well-known/agent-issuer`.
- The metadata document MUST include:
  - `issuer` — the canonical URL of the issuer
  - `jwks_uri` — URL of the JWKS document
  - `agent_registration_endpoint` — URL for agent registration
  - `agent_attestation_endpoint` — URL for attestation requests
  - `supported_signing_alg_values` — list of supported JWT signing algorithms
  - `supported_assertion_types` — MUST include `"agent+jwt"`
  - `spec_version` — version string of the AIS spec implemented

### RECOMMENDED

- The metadata document SHOULD include:
  - `supported_framework_values` — declared agent frameworks the issuer supports
  - `supported_environment_values` — e.g., `["development", "staging", "production"]`

---

## 2. JWKS Publication

### REQUIRED

- The issuer MUST publish a JWKS document at the URL declared in `jwks_uri`.
- The JWKS MUST include all active signing keys.
- Each key MUST include:
  - `kty`: key type (e.g., `"RSA"`)
  - `use`: `"sig"`
  - `alg`: signing algorithm (e.g., `"RS256"`)
  - `kid`: key identifier matching the `kid` header in issued JWTs
  - Key material: `n` and `e` for RSA keys

### RECOMMENDED

- The JWKS endpoint SHOULD be publicly accessible without authentication.
- Offline verifiers SHOULD be able to cache the JWKS and verify assertions without a live issuer call.

---

## 3. Agent Registration

### REQUIRED

- The issuer MUST provide a registration endpoint that:
  - Accepts at minimum: `org_id`, `team_id`, `display_name`, `framework`, `environment`
  - Returns a signed `agent+jwt` credential on success
  - Assigns a stable, globally unique `agent_id`

### RECOMMENDED

- The issuer SHOULD record the agent's `created_at` and `created_by` fields.
- The registration response SHOULD include the full `AgentIdentity` document alongside the credential.

---

## 4. Agent Assertions (agent+jwt)

### REQUIRED

- Issued tokens MUST be valid JWTs signed with a key declared in the issuer's JWKS.
- The JWT header MUST include:
  - `alg` — signing algorithm (MUST be `"RS256"` or stronger)
  - `kid` — key ID matching an entry in the issuer's JWKS
  - `typ` — MUST be `"agent+jwt"`
- The JWT payload MUST include:
  - `iss` — issuer identifier
  - `sub` — stable `agent_id`
  - `aud` — intended audience
  - `iat` — issued-at timestamp
  - `exp` — expiry timestamp
  - `jti` — unique token identifier
  - `agent_id` — same as `sub`
  - `org_id` — owning organization
  - `team_id` — owning team
  - `framework` — declared execution framework
  - `environment` — `development`, `staging`, or `production`

### RECOMMENDED

- Assertions SHOULD be short-lived (1 hour or less for production environments).
- The payload SHOULD include `display_name`.
- The payload MAY include `attestation_level`, `build_digest`, `runtime_class`, `tags`.

---

## 5. Offline Verification

### REQUIRED

A conformant verifier MUST be able to validate an agent assertion by:

1. Resolving the issuer's `/.well-known/agent-issuer` metadata document.
2. Retrieving the JWKS from `jwks_uri`.
3. Selecting the key whose `kid` matches the JWT header.
4. Verifying the JWT signature.
5. Checking that `exp` has not passed.
6. Validating required claims against local policy.

Verification MUST NOT require a synchronous call to the issuer beyond initial metadata and JWKS retrieval.

---

## 6. Credential Lifecycle

### REQUIRED

- The issuer MUST support credential expiry via `exp`.
- The issuer MUST support explicit agent revocation.

### RECOMMENDED

- The issuer SHOULD support credential rotation with a configurable overlap window to allow zero-downtime key transitions.
- The issuer SHOULD support explicit credential (jti-level) revocation in addition to agent-level revocation.
- The issuer MAY expose an introspection endpoint, but online introspection MUST NOT be required for verification.

---

## 7. Attestation Protocol

### REQUIRED

- A conformant issuer MUST support the two-step attestation flow:
  1. `POST {agent_attestation_endpoint}/challenge` — returns a short-lived challenge with a nonce.
  2. `POST {agent_attestation_endpoint}` — verifies the challenge response.
- The challenge MUST include: `challenge_id`, `issuer`, `audience`, `nonce`, `issued_at`, `expires_at`, `requested_claims`.
- The verifier MUST reject responses with a mismatched nonce.
- The verifier MUST reject responses to expired challenges.

### RECOMMENDED

- The verifier SHOULD verify the `agent_assertion` JWT in the attestation response against the JWKS.
- The verifier SHOULD report which requested claims were satisfied and which were missing.

### OPTIONAL

- The issuer MAY support hardware-backed evidence (TPM, enclave attestation).
- The issuer MAY support workload identity evidence (GCP, AWS, GitHub OIDC).
- The issuer MAY record attestation events in an audit log.

---

## 8. AgentIdentity Schema

The canonical `AgentIdentity` document MUST conform to the JSON Schema in [schema/agent-identity.schema.json](./schema/agent-identity.schema.json).

Required fields: `agent_id`, `org_id`, `team_id`, `display_name`, `framework`, `environment`, `created_at`, `created_by`, `status`, `tags`.

---

## 9. Security Requirements

- Private signing keys MUST remain under issuer control and MUST NOT be distributed to agents.
- Agent credentials MUST NOT inherit user permissions implicitly.
- Attestation claims MUST be treated as scoped statements, not universal trust grants.
- Issuers SHOULD rotate signing keys periodically and support overlap windows during rotation.
- Verifiers SHOULD enforce local policy on `framework`, `environment`, `audience`, and `attestation_level` in addition to signature validation.

---

## Conformance Summary Table

| Requirement | Level |
|---|---|
| `/.well-known/agent-issuer` discovery | REQUIRED |
| JWKS publication | REQUIRED |
| `agent+jwt` credential issuance | REQUIRED |
| Required JWT header fields (`alg`, `kid`, `typ`) | REQUIRED |
| Required JWT payload claims | REQUIRED |
| Offline verification (no live issuer call) | REQUIRED |
| Agent revocation | REQUIRED |
| Attestation challenge-response | REQUIRED |
| JWT verification in attestation | RECOMMENDED |
| Credential rotation with overlap | RECOMMENDED |
| Short-lived assertions (≤1h in production) | RECOMMENDED |
| Hardware-backed evidence | OPTIONAL |
| Audit log | OPTIONAL |
| Online introspection endpoint | OPTIONAL |
