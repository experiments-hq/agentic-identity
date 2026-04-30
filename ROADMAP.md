# Roadmap

## Now (v0.1)

**Ships today:**
- Open specification: agent identity model, issuer discovery, signed assertions, offline verification, attestation protocol
- Reference implementation (ACP): FastAPI server with all AIS endpoints + 7 governance primitives
- Verifier SDK (`ais-verify`): offline `agent+jwt` verification with policy enforcement
- Web governance console with identity registry, policy editor, audit viewer
- Docker one-liner demo with seeded data
- CI pipeline (GitHub Actions)

**In progress:**
- Go verifier SDK
- TypeScript / Node verifier SDK
- LangGraph and CrewAI framework integrations
- API gateway enforcement examples (Kong, Envoy, AWS API Gateway)

---

## Next (v0.2–v0.3)

- **ACP Cloud** — hosted agent identity infrastructure (managed issuer, credential lifecycle, multi-tenant)
- Enterprise SSO integration (SAML, OIDC federation)
- Multi-tenant organization and team management
- Framework SDK marketplace and gateway plugin registry
- Agent-to-agent authentication patterns
- Hardware-backed attestation (TPM, Nitro Enclaves, Confidential Compute)
- PostgreSQL deployment and Alembic migrations

---

## Later (v1.0+)

- Cross-issuer federation (multi-cloud, multi-vendor trust)
- Revocation at scale (CRL/OCSP equivalents for agent credentials)
- Compliance certifications (SOC 2, NIST AI RMF alignment)
- Model provenance claims (optional extension)
- Formal standards contribution (IETF, OpenID Foundation)

---

## Design Boundaries

AIS is the **identity and verification layer**. It answers: *who is this agent, who issued that identity, and can I verify it?*

What AIS deliberately leaves to the control plane:
- Authorization policy (allow/deny decisions)
- Agent orchestration and execution
- Model governance and evaluation
- Managed identity-as-a-service (that's ACP Cloud)
