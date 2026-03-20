# AIS Attestation Protocol

Version: `0.1-draft`

## 1. Purpose

OpenID Connect answers, "Who is this user or client?"

AIS attestation extends that idea for agents by answering, "What is this running agent instance, and what runtime properties can it prove right now?"

## 2. Protocol Shape

AIS uses a challenge-response pattern similar in spirit to token- and key-based internet identity protocols.

Participants:
- `Issuer`
- `Agent Runtime`
- `Verifier`

## 3. High-Level Flow

1. The verifier or issuer creates an attestation challenge.
2. The agent runtime signs the challenge response with its instance key or delegated signing material.
3. The response includes runtime claims.
4. The verifier validates the signature and challenge binding.
5. The verifier evaluates local trust policy.

## 4. Challenge Request

The challenge request should contain:
- `challenge_id`
- `issuer`
- `audience`
- `nonce`
- `issued_at`
- `expires_at`
- `requested_claims`

Example: [examples/attestation-request.json](c:/Users/nenye/acp/ais/examples/attestation-request.json)

## 5. Attestation Response

The response should contain:
- `challenge_id`
- `agent_assertion`
- `nonce`
- `evidence`
- `claims`
- `signature`

The `claims` object may include:
- `framework`
- `environment`
- `runtime_class`
- `build_digest`
- `container_digest`
- `deployment_id`
- `host_class`

Example: [examples/attestation-response.json](c:/Users/nenye/acp/ais/examples/attestation-response.json)

## 6. Verification Rules

The verifier should ensure:
- the challenge is fresh and unexpired
- `nonce` matches
- the assertion is valid
- the response signature is valid
- evidence maps to the same `agent_id`
- required claims satisfy local policy

## 7. Trust Model

AIS does not mandate a single evidence format. Evidence may come from:
- TPM- or enclave-backed attestation
- workload identity systems
- signed build provenance
- orchestrator-issued runtime proofs

This is intentional. The protocol standardizes envelope and verification shape, while allowing infrastructure-specific evidence mechanisms underneath.

## 8. OIDC Relationship

OIDC standardized identity and claims exchange for users and clients.

AIS attestation is analogous, but focused on:
- non-human machine actors
- runtime posture
- execution environment
- autonomous action safety

That makes it complementary to OIDC rather than a replacement.
