# Threat Model

This document describes the threats that AIS is designed to address and the mitigations built into the protocol.

---

## Trust boundaries

An AIS deployment has the following trust boundaries:

1. **Issuer → Agent**: The issuer trusts its own registration process and key management. The agent trusts the issuer to produce valid credentials.
2. **Agent → Verifier**: The agent presents a credential. The verifier should not trust the agent's self-reported claims beyond what the issuer signed.
3. **Verifier → Issuer (discovery)**: The verifier fetches metadata and JWKS from the issuer's well-known endpoint. This is a trust anchor.
4. **Attestation flow**: The verifier challenges the agent runtime to prove posture claims.

---

## Threats and mitigations

### T1: Token theft and replay

**Threat:** An attacker steals an `agent+jwt` and replays it to impersonate the agent.

**Mitigations:**
- Short-lived tokens (`exp` claim, default 24 hours in the reference implementation)
- `jti` claim for per-token uniqueness (revocation lists can track used JTIs)
- Transport-layer encryption (HTTPS) to prevent interception
- Revocation support: issuers can revoke credentials before expiry

**Residual risk:** Within the token's validity window and before revocation propagates, a stolen token can be replayed. This is inherent to the offline verification model and is the same trade-off OIDC access tokens make.

---

### T2: JWT algorithm confusion

**Threat:** An attacker modifies a token's `alg` header to `none` or to a symmetric algorithm (HS256), tricking a naive verifier into accepting an unsigned or attacker-signed token.

**Mitigations:**
- Verifiers must explicitly require `alg: RS256` and reject all other values
- The `ais_verify` SDK enforces this by checking the algorithm in the header before signature verification
- The `kid` header is required and verified against the issuer JWKS

**Implementation note:** The ACP reference implementation and `ais_verify` SDK both explicitly validate the algorithm header.

---

### T3: Discovery metadata substitution

**Threat:** An attacker intercepts or substitutes the `/.well-known/agent-issuer` response to redirect verifiers to a malicious JWKS.

**Mitigations:**
- Issuers must serve `/.well-known/agent-issuer` over HTTPS
- Verifiers should validate TLS certificates when fetching issuer metadata
- The `issuer` field in the metadata should match the URL used to fetch it

---

### T4: Attestation claim spoofing

**Threat:** An agent falsely reports runtime claims (e.g., `environment: production`, `runtime_class: cloud_run`) without actually running in that environment.

**Mitigations:**
- Static claims in the JWT (`environment`, `framework`) are set by the issuer at registration time, not by the agent
- Runtime attestation claims require a challenge-response flow with cryptographic evidence
- Verifiers should treat attestation claims as scoped statements that reflect the evidence provided, not as absolute guarantees

**Residual risk:** The current attestation protocol does not require hardware-backed evidence. Strong runtime attestation (TPM, Nitro Enclaves) is a planned enhancement.

---

### T5: Key material exposure

**Threat:** An attacker obtains the issuer's private signing key and forges arbitrary agent assertions.

**Mitigations:**
- Private keys should never be stored in plaintext (the reference implementation uses AES-256-GCM at rest)
- Key rotation should be supported and used regularly
- Compromise of a signing key requires rotating the key and revoking all credentials issued under it

---

### T6: Nonce replay in attestation

**Threat:** An attacker captures an attestation response and replays it to a different verifier.

**Mitigations:**
- Nonces are single-use and bound to a specific challenge ID
- Challenges have short expiry windows (5 minutes in the reference implementation)
- The `aud` claim in the agent assertion bounds the assertion to a specific verifier

---

### T7: Registration of unauthorized agents

**Threat:** An attacker registers a malicious agent with the issuer to obtain a valid credential.

**Mitigations:**
- The registration endpoint requires operator authentication (admin token or session)
- Registration should be restricted to trusted operator workflows
- Registered agents are logged with `created_by` attribution

---

## Out of scope

The following threats are explicitly out of scope for AIS:

- **Authorization policy**: AIS provides identity and verification. What an agent is allowed to do is the responsibility of the control plane and resource servers.
- **Model integrity**: AIS does not verify that an agent is running an approved model version. Model provenance is a planned extension.
- **Orchestration security**: AIS does not address threats in multi-agent orchestration (e.g., prompt injection, task hijacking).
- **Physical infrastructure security**: Key management hardware security is a deployment concern, not a protocol concern.

---

## Security properties AIS does not claim

- AIS does not guarantee that an agent will behave as intended — it only verifies its identity
- AIS does not prevent authorized agents from taking harmful actions
- AIS offline verification is not suitable for high-security contexts where a live revocation check is required for every request (use the optional introspection endpoint in those cases)
