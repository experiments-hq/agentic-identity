# Roadmap

AIS is currently at `0.1-draft`. This document tracks what needs to happen before the specification can be considered stable, and what we are building toward beyond that.

---

## Near-term (pre-1.0)

### Specification

- [ ] Tighten draft specification based on implementation and community feedback
- [ ] Complete conformance guidance (MUST / SHOULD / MAY table)
- [ ] Define normative claim vocabulary with precise semantics
- [ ] Mature attestation semantics for common runtime environments (Cloud Run, EKS, Lambda, Nitro Enclaves)
- [ ] Clarify cross-issuer trust model
- [ ] Add extensibility points for custom claims

### Reference implementation (ACP)

- [ ] Replace in-process approval wait with a webhook / callback model
- [ ] Add Alembic migrations for schema evolution
- [ ] PostgreSQL deployment documentation
- [ ] Multi-worker safe attestation challenge store (move from in-memory to DB)

### SDK

- [ ] Expand `ais_verify` to include an issuer SDK (not just verifier)
- [ ] Go verifier implementation
- [ ] TypeScript / Node verifier implementation

### Ecosystem

- [ ] LangGraph integration example
- [ ] CrewAI integration example
- [ ] API gateway enforcement examples (Kong, Envoy, AWS API Gateway)
- [ ] Framework adapter interface definition
- [ ] Conformance test suite

---

## Medium-term

- Hardware-backed attestation semantics (TPM, Nitro Enclaves, Cloud Confidential Compute)
- Agent-to-agent authorization model
- Revocation at scale (CRL / OCSP equivalents for agent credentials)
- Cross-issuer federation design
- Model provenance claims (optional extension)
- Standardized delegation chain representation

---

## What AIS will not do

AIS is an identity layer. It is explicitly not trying to:

- Define authorization policy (that is the control plane's job)
- Replace OIDC or OAuth for human users
- Specify agent orchestration or execution
- Provide a managed identity service
- Define model governance or evaluation standards

---

## Versioning

AIS follows SemVer:
- **Patch** — clarifications, example corrections, non-normative changes
- **Minor** — new optional features, backward-compatible normative additions
- **Major** — breaking changes to required claims, flows, or protocol structure
