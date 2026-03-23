# AIS: Toward a Standard Trust Layer for AI Agents

*A candidate interoperability standard for representing AI agents as first-class principals across runtimes, gateways, policy engines, and enterprise control planes.*

---

The AI ecosystem has invested heavily in the reasoning capabilities of agents — how they plan, use tools, decompose tasks, and recover from errors. At the same time, a parallel conversation has begun to take shape around a more foundational systems question: what is an AI agent as a security principal, and how can the rest of a system verify that identity without bespoke integration?

That question is no longer theoretical. It is becoming a deployment constraint.

As agents move from research demos into production workflows, enterprises need a standard way to identify, scope, audit, and trust autonomous systems across vendors and environments. Without that layer, every deployment becomes a custom integration problem: gateways cannot reliably distinguish agent calls from generic service traffic, policy engines lack portable claims to reason over, and post-incident attribution becomes unnecessarily difficult.

This gap is increasingly visible in both industry practice and standards work. Security teams are reporting incidents involving autonomous systems operating with excessive permissions or weakly bounded authority, while standards bodies and identity practitioners are beginning to ask how agents should be represented within existing trust architectures. What remains unsettled is not whether agent identity matters, but how to represent it in a portable, interoperable, and operationally useful way.

This post argues that the ecosystem needs a standard identity layer for AI agents and proposes a concrete starting point: the **Agent Identity Specification (AIS)**.

AIS is not presented here as the first recognition of the problem. Rather, it is a specific implementation-oriented proposal within an emerging but still unconverged design space.

---

## Why Now

Standards become most consequential when a new systems layer is beginning to ossify.

That is where AI agents appear to be now. Framework-local conventions can still work in early experimentation, but they do not scale across gateways, policy engines, cloud environments, model providers, and enterprise control planes. If the ecosystem waits too long, today's ad hoc identity patterns — shared API keys, borrowed user credentials, generic service accounts, framework-specific metadata — will harden into tomorrow's interoperability tax.

The value of a standard here is not only security. It is coordination leverage. A shared identity layer would reduce integration cost for vendors, increase portability for customers, and create a common trust substrate for agent-to-agent and agent-to-service interactions.

The problem, then, is not whether existing building blocks exist. They do. The problem is that they do not yet converge on a single agent-native trust representation that heterogeneous systems can consume consistently.

---

## The Gap in the Current Landscape

The agent identity problem has at least three distinct layers, and much of the current confusion comes from collapsing them into one.

**1. Principal definition.**
What claims actually constitute an agent's identity? For human users, the answer is mature: a subject identifier, an issuer, and a set of verified attributes. For workloads, the answer is also relatively mature in several ecosystems. For AI agents, however, there is still no clear consensus on which properties should be treated as canonical, portable, or security-relevant.

Claims such as `framework`, `environment`, `runtime_class`, `build_digest`, `operator`, `delegation_scope`, and `attestation_level` are all plausible first-class attributes. But there is no widely adopted schema defining which of these claims should be standardized, how they should be interpreted, or which systems should rely on them.

**2. Credential format and verification.**
How is an agent's identity represented in a portable credential, and how can a downstream verifier validate it without introducing availability dependencies on the issuer? Existing cryptographic primitives already solve much of this problem — signed JWTs and JWKS-based verification are sufficient in principle. What the ecosystem still lacks is an agent-native assertion type and a claims vocabulary designed specifically for autonomous principals.

**3. Runtime attestation.**
A registered identity answers one question: what does the issuer say this agent is? A different and often more operationally important question is: what can this running instance prove about its current execution context right now? That requires a challenge-response protocol capable of binding fresh runtime evidence to the registered identity.

These layers are related, but they are not interchangeable. A useful ecosystem standard needs to distinguish them clearly: identity registration, portable credential verification, and live execution attestation.

---

## Prior Art and Differentiation

AIS enters an active field rather than an empty one. Several adjacent efforts already address parts of the problem, and any credible proposal should be explicit about where it overlaps with prior work and where it differs.

### OpenID Connect, OAuth, and emerging agent identity work

The closest architectural precedent is OpenID Connect (OIDC), which solved a similar coordination problem for user identity on the web.[^4] More recently, identity practitioners and standards groups have begun applying related thinking to agentic systems: how autonomous software should authenticate, how it should be authorized, and how it should be distinguished from both human users and generic applications.

AIS is strongly influenced by this tradition. Its issuer model, discovery pattern, and offline verification approach are intentionally OIDC-shaped.

But AIS differs in scope and semantics. OIDC is optimized for human authentication and delegated user-facing application flows. Its claims vocabulary describes properties of login and delegation events, not properties of autonomous systems running in enterprise or multi-agent execution contexts. AIS therefore proposes an agent-native assertion profile rather than reusing OIDC tokens unchanged.

### SPIFFE/SPIRE and workload identity

SPIFFE and SPIRE provide one of the strongest existing models for workload identity. They solve an important part of the problem already: assigning cryptographically verifiable identities to software workloads and binding those identities to attested infrastructure and runtime properties.

AIS is compatible with that model and should be understood as complementary rather than competitive.

The key distinction is semantic level. SPIFFE identities describe workloads within a trust domain. AIS is aimed at a higher-level agent principal that may need to carry additional claims meaningful to gateways, policy engines, auditors, and cross-framework orchestration systems — claims such as `framework`, declared `environment`, team ownership, or agent-specific attestation state.

SPIFFE is a strong candidate evidence source or substrate for AIS deployments, but it does not by itself define the full portable semantics of an autonomous agent principal.

### Verifiable credentials and decentralized identity

Verifiable credential systems and DID-based approaches offer another relevant body of prior art. They are well-suited for portable signed assertions and cross-domain verifiability, and they may become important in federated or inter-organizational agent ecosystems.

AIS does not reject that direction. It simply chooses a narrower operational starting point: a web-native issuer, JWT-style credentials, JWKS-based verification, and an attestation interface designed for immediate deployment in existing enterprise infrastructure. This is a design choice in favor of incremental adoption, not a claim that VC-based systems are unimportant.

### What AIS claims to add

AIS should therefore be understood not as "the first system to notice agent identity," but as a concrete proposal for the following combination:

- an agent-native assertion type (`agent+jwt`)
- a compact standard claims vocabulary for autonomous principals
- OIDC-like issuer metadata and JWKS discovery
- offline verification suitable for gateways and policy engines
- a separable attestation interface for live runtime evidence
- a deployment model that composes with existing identity, workload, and policy systems

That combination is the core differentiator.

---

## What OIDC Got Right

Even with the prior-art context established, OIDC remains the closest successful precedent for the coordination problem AIS is trying to solve.

Before OIDC, web applications faced a familiar pattern: fragmented identity systems, bilateral federation work, no common discovery mechanism, and no standard credential that relying parties could verify from published metadata alone.

OIDC solved that problem with four architectural decisions that matter here as well:

- **issuer-based trust** — any relying party that trusts the issuer can trust credentials the issuer signs
- **discovery metadata** — a self-describing `/.well-known/` endpoint exposes issuer capabilities
- **offline verification** — published JWKS keys allow credential verification without synchronous callbacks
- **portable signed assertions** — JWTs provide a common credential format with a shared claims vocabulary

AIS is intentionally modeled on OIDC's architecture, but not its semantics. OIDC is optimized for human authentication flows. Its core claims and assurance vocabulary describe properties of a user login event, not properties of an autonomous system operating in a runtime context. Reusing OIDC unchanged would force agent semantics into fields that were not designed for them, producing fragile and non-portable implementations.

The right approach is to preserve OIDC's successful trust architecture while defining an agent-native assertion type, agent-specific claims vocabulary, and attestation interface.

---

## A Proposed Specification: AIS

The Agent Identity Specification (AIS) is an open, implementation-oriented standard for representing AI agents as first-class security principals across runtimes, gateways, and enterprise control planes.

| OpenID Connect | AIS |
|---|---|
| OpenID Provider | Agent Issuer |
| ID Token | Agent Assertion (`agent+jwt`) |
| Discovery Metadata | Agent Issuer Metadata |
| JWKS URI | Agent JWKS URI |
| User Claims | Agent Claims |
| Authentication Context | Attestation Context |

AIS is designed to be minimally disruptive. It does not replace OAuth, OIDC, cloud workload identity, service mesh identity, or policy engines. Instead, it provides an agent-specific identity layer those systems can consume.

In practice, AIS assertions can be verified at an API gateway, consumed by a policy engine, logged for attribution and audit, combined with stronger runtime evidence where needed, and exchanged across heterogeneous agent frameworks without framework-local conventions.

An AIS-conformant issuer exposes four logical interfaces:

```
GET  /.well-known/agent-issuer    →  issuer metadata (capabilities, JWKS URI, endpoints)
GET  /.well-known/jwks.json       →  public keys for offline-verifiable credentials
POST /api/agents/register         →  issues a signed agent+jwt
POST /v1/attestations/challenge   →  runtime challenge-response attestation
```

AIS defines an agent-native assertion type, `agent+jwt`, so that agent credentials are distinguishable from access tokens and user identity tokens at the JOSE header level. That distinction is operationally important: gateways, policy engines, and downstream services should be able to detect that they are receiving an agent principal — not a human principal and not a generic service credential.

The initial required claims are intentionally small: enough to establish issuer-scoped identity, organizational ownership, and deployment context. Required claims include `agent_id`, `org_id`, `team_id`, `framework`, `environment`, and standard JWT temporal fields (`iss`, `sub`, `aud`, `iat`, `exp`, `jti`). Optional claims include `build_digest`, `runtime_class`, and `attestation_level`. The broader claims vocabulary should evolve through implementation experience and standardization, rather than being overfit prematurely.

A concrete registration and the resulting token:

```http
POST /api/agents/register
Content-Type: application/json

{
  "org_id": "org-acme",
  "team_id": "team-finance",
  "display_name": "Payments Reconciliation Agent",
  "framework": "langgraph",
  "environment": "production"
}
```

```json
{
  "iss": "https://acp.example.com",
  "sub": "5f8d9f32-0c4f-4d2a-8b4f-0c27680e41f8",
  "aud": "https://gateway.example.com",
  "iat": 1773642000,
  "exp": 1773645600,
  "jti": "bdfe8437-c7b9-4e4e-a385-229949d34d2d",
  "agent_id": "5f8d9f32-0c4f-4d2a-8b4f-0c27680e41f8",
  "org_id": "org-acme",
  "team_id": "team-finance",
  "framework": "langgraph",
  "environment": "production"
}
```

This is the shift away from today's common pattern of shared API keys or generic service accounts: the credential identifies a specific autonomous principal with explicit organizational and deployment context.

Verification is offline by design. A verifier resolves the issuer's JWKS once, caches it, and validates subsequent assertions cryptographically without requiring a round-trip to the issuer. This is not merely an optimization. At agent-to-agent call volumes, synchronous token introspection creates unacceptable latency, operational coupling, and failure modes.

```python
from ais_verify import AgentVerifier

verifier = AgentVerifier(issuer="https://acp.example.com")
claims = await verifier.verify(token, required_environment="production")

print(claims.agent_id)      # "5f8d9f32-..."
print(claims.framework)     # "langgraph"
print(claims.environment)   # "production"
```

---

## The Attestation Protocol

The registration assertion answers one foundational question: what agent principal does the issuer recognize?

Attestation answers a different one: what can this live instance prove about its present execution context?

AIS defines a nonce-bound challenge-response protocol for this separation:

```http
POST /v1/attestations/challenge
{ "requested_claims": ["framework", "environment", "build_digest"] }

→ { "challenge_id": "...", "nonce": "abc123", "expires_at": "..." }

POST /v1/attestations
{
  "challenge_id": "...",
  "nonce": "abc123",
  "agent_assertion": "<jwt>",
  "claims": {
    "framework":    "langgraph",
    "environment":  "production",
    "build_digest": "sha256:5b8e43d2..."
  }
}

→ { "verified": true, "jwt_verified": true, "attestation_level": "assertion_verified" }
```

This separation matters because many production controls depend not just on who the agent is, but on where and how it is running: production vs. staging, approved build vs. unknown build, expected runtime vs. unexpected execution context.

The nonce binding provides freshness — the response is tied to a specific challenge window and cannot be replayed as stale evidence. The verifier specifies which claims it requires; the agent does not self-select what to disclose. The JWKS-backed signature check ties the attestation response back to the registered agent identity.

The base protocol supports software-level claims first. Stronger evidence sources — TPM quotes, confidential-compute attestations, cloud workload identity documents, SPIFFE-derived workload evidence, or OIDC-linked build provenance — fit into the same `evidence` interface. AIS therefore acts as a normalization layer: it does not try to replace every evidence system, but to give verifiers a standard way to consume agent identity plus evidence across heterogeneous environments.

---

## Compatibility and Non-Goals

AIS is designed to compose with existing infrastructure rather than replace it. It is compatible in principle with OIDC and OAuth-based enterprise identity systems, cloud workload identity and workload federation, SPIFFE/SPIRE-style workload identity, API gateways and service meshes, policy engines such as OPA or Cedar, agent runtimes and orchestration frameworks, and audit, observability, and governance layers.

AIS does not attempt to do everything. Its non-goals are equally important: it does not replace authorization policy engines, does not mandate a single attestation technology, does not define full orchestration semantics for agents, does not require greenfield replacement of existing identity infrastructure, and does not claim to supersede workload identity or verifiable credential systems.

Its purpose is narrower and, for that reason, more actionable: to define an interoperable trust representation for agent principals.

---

## Open Problems and Research Directions

AIS is deployable without solving every downstream research problem. The core registration-and-verification model is implementable now. The following questions define the frontier for broader federation, stronger assurance, and richer policy composition.

**Cross-issuer trust.** AIS 0.1 assumes a single issuer trust domain. In practice, high-value agent workflows will span multiple organizations, clouds, and control planes. SPIFFE/SPIRE, federated OIDC, and verifiable credential ecosystems all provide useful reference points. Whether one of those models transfers cleanly — or whether agent ecosystems need a hybrid trust architecture — remains open.

**Hardware-backed attestation semantics.** The protocol can carry stronger evidence, but the semantics are not yet standardized. What exactly does `build_digest` attest to? How should enclave or TPM measurements be interpreted? What assurance taxonomy should `attestation_level` represent? Formalizing that trust hierarchy is a natural next step for the spec.

**Agent-to-agent authorization.** AIS establishes identity, not policy. That separation is deliberate. But in practice, the value of identity is realized only when policy engines can consume AIS claims consistently. Defining common integration patterns with authorization systems — OPA, Cedar, gateway-native policy engines, and capability models — is likely to be one of the most important practical extensions.

**Revocation and lifecycle management at scale.** Short-lived assertions handle many revocation scenarios, but large multi-agent systems introduce harder operational questions: key rotation, issuer rollover, revocation propagation, overlap windows, and recovery after compromise.

**Claim standardization and semantic drift.** Even if the transport and verification model converge, the ecosystem may still fragment at the claims layer. Terms like `framework`, `runtime_class`, `operator`, and `delegation_scope` will need consistent semantics to be portable across implementations. A future version of AIS may therefore need a stricter registry or extension model for claims.

---

## Implementation

AIS is backed by a working reference implementation, verifier SDK, and conformance materials rather than a paper-only design.

The repository is at: **[github.com/experiments-hq/agentic-identity](https://github.com/experiments-hq/agentic-identity)**

It contains:

- **Normative specification and conformance requirements** — `spec/SPEC.md`, `spec/ATTESTATION.md`, `spec/CONFORMANCE.md`
- **Standalone verifier SDK** (`ais-verify`) — offline `agent+jwt` verification with minimal dependencies
- **Reference control plane implementation** — FastAPI + SQLite server implementing all AIS-required endpoints
- **Canonical JSON Schema** for the AgentIdentity document
- **Self-contained protocol demo** (`python demo/demo.py`) for an end-to-end walkthrough

The intended deployment path is incremental. Organizations can begin by issuing and verifying AIS assertions at trust boundaries such as gateways or tool brokers, then layer in policy consumption and stronger attestation for higher-risk workflows. This makes AIS suitable for phased adoption rather than all-or-nothing replacement.

The conformance requirements in `spec/CONFORMANCE.md` use RFC 2119 MUST/SHOULD/MAY language and define a concrete implementer checklist. The design rationale for major decisions is documented in [`docs/problem.md`](https://github.com/experiments-hq/agentic-identity/blob/main/docs/problem.md).

---

## Closing Argument

The agent ecosystem today resembles other pre-convergence periods in infrastructure standards: multiple teams recognize the same trust problem, several adjacent solutions exist, and no single representation has yet become the default across vendors, frameworks, and control planes.

That fragmentation already produces measurable costs — security incidents, weak attribution, brittle integrations, and deployment friction for enterprises trying to scale autonomous systems safely.[^1][^2][^3]

OIDC demonstrated that a new principal type becomes tractable only when the ecosystem agrees on a trust architecture, a portable assertion format, and a standard verification model. AI agents now appear to need an equivalent layer — though one adapted to autonomous software rather than human authentication.

AIS is an attempt to define that layer early enough for the ecosystem to converge before fragmentation hardens into de facto incompatibility. It is not the only relevant effort in this space, nor does it claim to replace the many systems that already solve adjacent problems. Its claim is narrower: that agent ecosystems would benefit from a dedicated, interoperable trust representation for agent principals, and that such a representation can be made concrete today.

If the goal is a future in which agents can interoperate across vendors, clouds, frameworks, and control planes with clear identity and verifiable trust, then standardizing the agent principal remains one of the highest-leverage places to start.

Contributions to the specification and implementation are welcome. Particularly valuable next steps would include review from agent framework authors, gateway vendors, model providers, cloud security teams, workload identity practitioners, and identity standards groups.

See [`CONTRIBUTING.md`](https://github.com/experiments-hq/agentic-identity/blob/main/CONTRIBUTING.md) and [`RATIONALE.md`](https://github.com/experiments-hq/agentic-identity/blob/main/RATIONALE.md) for contribution guidance and design context.

---

### References

[^1]: Gravitee. *State of AI Agent Security 2026: When Adoption Outpaces Control.* [gravitee.io/state-of-ai-agent-security](https://www.gravitee.io/state-of-ai-agent-security). Statistics cited: 88% of organizations reported a confirmed or suspected AI agent security incident in the last year; 21.9% treat AI agents as independent identity-bearing entities; 45.6% rely on shared API keys for agent-to-agent authentication.

[^2]: CyberArk. *AI Agents and Identity Risks: How Security Will Shift in 2026.* [cyberark.com/resources/blog/ai-agents-and-identity-risks-how-security-will-shift-in-2026](https://www.cyberark.com/resources/blog/ai-agents-and-identity-risks-how-security-will-shift-in-2026). The financial services case (prompt injection via shipping address field → unauthorized invoicing tool access → data exfiltration) is cited directly in this post; CyberArk attributes root causes as excessive permissions and lack of input filtering.

[^3]: OWASP Gen AI Security Project. *OWASP Top 10 for LLM Applications 2025 — LLM06: Excessive Agency.* [owasp.org/www-project-top-10-for-large-language-model-applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/). LLM06 defines Excessive Agency as damaging actions enabled by excessive functionality, excessive permissions, or excessive autonomy granted to LLM-based agents.

[^4]: OpenID Foundation. *OpenID Connect Core 1.0.* Published November 8, 2014. [openid.net/specs/openid-connect-core-1_0.html](https://openid.net/specs/openid-connect-core-1_0.html).
