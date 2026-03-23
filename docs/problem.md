# AIS Design Rationale

This document explains the problems AIS was designed to solve, the constraints that shaped its design, and the reasons key decisions were made the way they were.

---

## The Problem

AI agents are being deployed at scale to take real-world actions: calling APIs, executing code, reading databases, sending messages, making purchases, modifying infrastructure.

These agents have no standardized identity.

Today, an agent is typically represented as one of:
- a **shared API key** — no provenance, no expiry semantics, no way to know which agent issued a call
- a **service account** — designed for services, not autonomous reasoners; no claims about framework, environment, or runtime behavior
- a **user account** — the agent inherits a human's permissions, blurring the principal boundary entirely
- a **framework-specific opaque ID** — LangGraph, AutoGen, CrewAI, and others each have their own concepts, none interoperable

The result is that every enterprise building with agents has to invent its own identity model from scratch, and every gateway, tool, or API receiving agent requests has no standard way to answer:

- **Who is this agent?** (not just "what process", but: which organization, team, framework, environment, version)
- **Is this credential still valid?**
- **What can this agent attest to about its own runtime posture?**
- **Can I verify this offline, without calling a vendor control plane?**

This is the identity gap. AIS is designed to close it.

---

## Why Not Extend OAuth / OIDC Directly?

OpenID Connect solved an equivalent problem for user identity in 2014. It is the obvious reference point.

The answer is not "instead of OIDC" but "shaped like OIDC, adapted for agents."

OIDC is not a sufficient fit for three reasons:

**1. OIDC is optimized for human login flows.**
ID tokens carry user claims: email, name, locale, phone. The OIDC `sub` is a user subject. The OIDC `acr` captures authentication context (password vs. MFA vs. hardware token), not runtime posture. None of these map cleanly to an agent that has no login event, no email address, and whose "authentication context" is really about build provenance and execution environment.

**2. OIDC does not define non-human principal semantics.**
The specification is silent on what it means for a principal to be autonomous, to invoke tools, to take actions on behalf of no specific user, or to have a `framework` or `environment` as first-class identity claims. Reusing OIDC directly means either overloading existing fields with agent-specific meaning (fragile) or using custom claims with no interoperability (pointless).

**3. OIDC's `Authentication Context Reference` (`acr`) is not attestation.**
OIDC `acr` describes how the user authenticated. AIS attestation is a challenge-response protocol in which the agent instance proves runtime facts to a verifier — a fundamentally different model. An agent can attest its framework, environment, build digest, and runtime class. This requires a distinct protocol, not a repurposing of `acr`.

What AIS takes from OIDC:
- issuer-based trust model
- `/.well-known/` discovery
- JWKS-published verification keys
- signed JWTs as the portable credential format
- offline-verifiable tokens (no synchronous issuer callback required)

These are the right primitives. AIS applies them to a new principal type.

---

## Why `agent+jwt` as the Token Type?

RFC 7519 (JWT) allows the `typ` header to carry a media type. Using `typ: "agent+jwt"` does two things:

1. It makes the credential self-describing. Any verifier that inspects a token header immediately knows this is an agent assertion, not an ID token or an access token.
2. It creates a namespace for future sub-types (e.g., `agent+jwt;class=ephemeral`) without breaking existing parsers.

The alternative — reusing `typ: "JWT"` or `typ: "at+jwt"` — would conflate agent assertions with existing token types and require consumers to infer principal type from claims alone.

---

## Why RS256 as the Default Signing Algorithm?

RS256 (RSASSA-PKCS1-v1_5 with SHA-256) was chosen as the required minimum for three reasons:

1. **Ubiquitous support.** RS256 is implemented in every major JWT library across every language. Ed25519 is preferable on performance grounds but is not universally supported, particularly in enterprise Java and .NET ecosystems that AIS targets.

2. **JWKS interoperability.** RSA public keys have a well-defined, widely implemented JWKS representation (`n`, `e`). The JWKS format for Ed25519 (`OKP` key type) is less consistently supported.

3. **Upgrade path.** The `supported_signing_alg_values` field in issuer metadata allows issuers to advertise Ed25519 or ES256 support alongside RS256. Conformant verifiers that support stronger algorithms can prefer them; others fall back to RS256.

---

## Why Offline Verification?

The decision that verification MUST NOT require a synchronous call to the issuer beyond initial metadata and JWKS retrieval is fundamental to the design.

The alternative — online introspection on every token use — creates:
- **availability coupling**: if the issuer is unavailable, every downstream verification fails
- **latency cost**: every agent invocation pays an additional network round-trip
- **vendor lock-in**: systems can only operate when connected to their specific issuer

Offline verification means:
- a gateway can cache the JWKS and verify thousands of agent calls per second with no issuer involvement
- systems can operate in network-partitioned environments (edge, on-prem, air-gapped)
- the trust model is cryptographic, not operational

AIS does allow issuers to expose an optional introspection endpoint for revocation lookups. But the baseline verification path must work offline.

---

## Why `/.well-known/agent-issuer`?

The `/.well-known/` URI convention (RFC 5785) is the established standard for publishing metadata about a server. OIDC uses `/.well-known/openid-configuration`. OAuth 2.0 Authorization Server Metadata (RFC 8414) uses `/.well-known/oauth-authorization-server`.

Using `/.well-known/agent-issuer` follows this convention and allows:
- verifiers to discover an issuer's capabilities with a single predictable GET
- existing infrastructure (reverse proxies, CDNs, monitoring) to handle the endpoint without special configuration

The alternative — requiring the issuer to publish its metadata URL out-of-band — would break the self-describing property of the protocol and require bilateral configuration that prevents true interoperability.

---

## Why a Separate Attestation Protocol?

Agent assertions answer: *who is this agent, per its issuer?*

Attestation answers: *what can this running instance prove about itself right now?*

These are distinct questions. An agent assertion is issued at registration time or credential renewal. Attestation is a runtime operation — the agent instance responds to a fresh challenge with signed claims about its current execution context.

The challenge-response design (rather than self-attested claims embedded in the assertion) is deliberate:
- **freshness**: the nonce binds the response to a specific point in time, preventing replay
- **verifier-driven**: the verifier specifies which claims it needs; the agent does not decide what to disclose
- **escalation path**: basic attestation can be satisfied by framework + environment claims; hardware-backed evidence (TPM, enclave) plugs in at the same interface

---

## Why Not Define a Policy Engine?

The AIS scope boundary is deliberate. AIS standardizes *what an agent is* and *how its identity is verified*. It does not standardize what to *do* with a verified identity.

Policy — allow/deny rules, approval workflows, budget limits, rate limits — is intentionally out of scope. Organizations have wildly different policy requirements, and a policy standard layered on top of identity would either be too prescriptive (limiting adoption) or too abstract (useless).

The Agent Control Plane (ACP) in this repository provides one policy model. Other control planes, gateways, and enterprise systems should be able to consume AIS identities and enforce their own policies.

This is the same boundary OIDC drew: it standardizes how you get a verified identity, not what your application does with it.

---

## Relationship to Existing Work

| Standard / Framework | Relationship |
|---|---|
| OpenID Connect (OIDC) | AIS is intentionally shaped like OIDC. AIS borrows the issuer trust model, discovery convention, and JWKS-based offline verification. AIS is not a profile of OIDC. |
| OAuth 2.0 | AIS does not define an OAuth flow. An AIS issuer may also be an OAuth authorization server; the two coexist without conflict. |
| SPIFFE/SPIRE | SPIFFE addresses workload identity in service mesh environments. AIS addresses agent identity as a first-class principal type. The two are complementary: SPIFFE can establish platform identity, AIS establishes agent identity layered on top. |
| W3C Verifiable Credentials | VCs are a general-purpose credential format. AIS is a specialized protocol for agent identity, optimized for JWT infrastructure and JWKS-based offline verification rather than the DID/VC ecosystem. |
| NIST AI RMF | AIS attestation supports auditability and provenance requirements in frameworks like NIST AI RMF 1.0 and the EU AI Act by enabling verifiable records of agent identity and runtime posture. |

---

## What AIS Does Not Solve

Being explicit about non-goals prevents scope creep and misuse:

- **Authorization**: AIS establishes identity. It does not specify what a verified agent is permitted to do.
- **Orchestration**: How agents are composed, scheduled, or chained is outside scope.
- **Model provenance**: AIS can carry a `build_digest` claim, but it does not define what that digest covers or how it was computed.
- **Cross-issuer federation**: AIS 0.1 does not specify how trust is established between two independent issuers.
- **Key management infrastructure**: AIS specifies the interface (JWKS); it does not mandate how issuers manage their signing keys internally.

---

## Status and Stability

AIS 0.1-draft describes a protocol whose shape is stable. The design decisions above are considered settled. Field names, endpoint paths, and specific claim values may change before a 1.0 release based on implementation experience and community feedback.

The conformance requirements in [CONFORMANCE.md](./ais/CONFORMANCE.md) define exactly what is required, recommended, and optional for any implementation to be AIS-conformant.
