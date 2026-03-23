# Comparison

How AIS relates to other identity and authentication approaches.

---

## OIDC / OpenID Connect

**The closest analogy.** AIS borrows heavily from OIDC's trust architecture: an issuer model, `/.well-known/` discovery, JWKS, signed JWTs, and offline verification. The core difference is the principal type.

OIDC is designed for **human login flows**. It models the relationship between a user, a client application, and a resource server. The subject (`sub`) is always a human user.

AIS models **autonomous agents** as the primary principal. Agents are not users and do not fit cleanly into OIDC's authorization code flow or the human consent model. AIS removes concepts that do not apply (session management, refresh tokens, user consent) and adds concepts that do (framework claims, environment claims, attestation).

**Summary:** AIS uses OIDC's trust architecture but applies it to a different principal type.

---

## OAuth 2.0 client credentials

OAuth client credentials authenticate a **software client** (not a user) to access a resource. This is the most common current approach for agent authentication.

The limitation: client credentials authenticate an application identity, not an agent identity. Two different agents from the same application share the same client identity. There is no standard way to express agent-specific attributes (framework, environment, team, attestation level) in an OAuth client credential.

**Summary:** Client credentials work for application-level auth. AIS provides agent-level identity with richer claims and offline verification semantics.

---

## Service accounts

Service accounts (Google Cloud, Kubernetes, AWS IAM roles) authenticate workloads to cloud services. They are widely used and well-understood.

The limitations for agents:
- Service accounts are usually scoped to a service, not an individual agent instance
- They do not carry agent-specific metadata (framework, environment, team)
- They are typically platform-specific and not portable across systems
- They do not include an attestation model for runtime verification

**Summary:** Service accounts solve access control within a platform. AIS is designed to be portable across platforms and to carry richer identity semantics.

---

## SPIFFE / SPIRE

SPIFFE is a standard for **workload identity** in distributed systems. A SPIFFE Verifiable Identity Document (SVID) asserts the identity of a workload (service, pod, process) using X.509 certificates or JWTs.

SPIFFE and AIS are **complementary**. SPIFFE answers "what workload is running on this infrastructure?" AIS answers "what agent is this, who issued its identity, and what runtime posture can it prove?" An agent could have both a SPIFFE identity (for infrastructure-level mTLS) and an AIS identity (for application-level agent trust decisions).

**Summary:** SPIFFE is infrastructure-level workload identity. AIS is application-level agent identity. They operate at different layers.

---

## W3C Verifiable Credentials

W3C VCs provide a general-purpose format for cryptographically verifiable claims. They are designed around a holder/issuer/verifier model with a focus on privacy-preserving selective disclosure.

W3C VCs are a capable framework but optimized for a different operational context: credential wallets, human subjects, privacy features, and decentralized identifiers. For autonomous agents making high-frequency API requests, the operational profile is different — agents need compact, fast-to-verify credentials with a standard discovery model that integrates with existing HTTP infrastructure.

**Summary:** W3C VCs are a general-purpose credential format. AIS is purpose-built for the agent identity use case with HTTP-native discovery and verification.

---

## Application JWTs

Many teams issue custom JWTs for their agents as an ad hoc solution. This works but creates proprietary, non-interoperable identity schemes. Each system has different claim names, different issuers, and different verification logic.

AIS standardizes the claim vocabulary, discovery mechanism, and verification protocol so that different control planes, gateways, and frameworks can interoperate.

**Summary:** Application JWTs are the current status quo. AIS is an attempt to standardize what everyone is already doing ad hoc.

---

## Summary table

| Approach | Principal type | Offline verification | Agent-specific claims | Attestation | Portability |
|---|---|---|---|---|---|
| OIDC | Human user | Yes | No | No | High |
| OAuth client credentials | Software client | Partial | No | No | Medium |
| Service accounts | Workload / service | Depends on platform | No | No | Low |
| SPIFFE / SVID | Workload | Yes (X.509) | No | No | Medium |
| W3C VCs | General (human focus) | Yes | Custom | Partial | High |
| Application JWTs | Ad hoc | Depends | Custom | No | Low |
| **AIS** | **Autonomous agent** | **Yes** | **Yes** | **Yes** | **High** |
