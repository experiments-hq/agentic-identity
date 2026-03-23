# Security Policy

## Reporting a Vulnerability

AIS is a security-sensitive protocol. If you discover a vulnerability in the specification, reference implementation, or SDK, please report it responsibly.

**Do not file a public GitHub issue for security vulnerabilities.**

Use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) for this repository, or contact the maintainers directly via the email listed in the GitHub profile.

Include in your report:
- A clear description of the vulnerability
- Steps to reproduce or a proof-of-concept
- Your assessment of severity and impact
- Any suggested mitigations

We will acknowledge reports within 48 hours and aim to provide a resolution timeline within 7 days.

---

## Supported Versions

| Component | Supported |
|---|---|
| `spec/` (AIS specification) | `0.1-draft` and later |
| `acp/` (reference implementation) | latest `main` |
| `sdk/ais_verify` | latest `main` |

The `0.1-draft` specification is in active development. Security issues that affect the protocol design are especially important to disclose before the specification stabilizes.

---

## Scope

### In scope
- Vulnerabilities in the AIS protocol specification (e.g., algorithm confusion, replay attack vectors, claim spoofing)
- Vulnerabilities in the ACP reference implementation (`acp/`)
- Vulnerabilities in the `ais_verify` SDK
- Issues with cryptographic primitive usage

### Out of scope
- Vulnerabilities in third-party dependencies (report to the upstream project)
- Issues requiring physical access to the deployment environment
- Social engineering

---

## Security Considerations for Implementers

For the protocol-level threat model, see [`docs/threat-model.md`](docs/threat-model.md).

Key areas of concern for AIS deployments:

- **JWT algorithm confusion** — verifiers must enforce `alg: RS256` and reject `none` or symmetric algorithms
- **Key material exposure** — private signing keys must remain under issuer control
- **Attestation claim spoofing** — attestation claims are scoped statements, not universal trust grants
- **Challenge replay** — nonces must be single-use and bound to a short expiry window
- **Discovery metadata substitution** — issuers should serve metadata over HTTPS with valid certificates

---

## Cryptographic Primitives

AIS currently specifies:
- **RS256** (RSASSA-PKCS1-v1_5 with SHA-256) for assertion signing
- Challenge-response nonce binding for attestation

The reference implementation additionally uses:
- **AES-256-GCM** for private key storage at rest
- **SHA-256** for key fingerprinting and audit chain integrity

Ed25519 (`EdDSA`) is planned as an upgrade path via `supported_signing_alg_values`.
