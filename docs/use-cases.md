# Use Cases

Practical scenarios where AIS provides value.

---

## Internal tool and API access

**Scenario:** An agent needs to call internal APIs — payment services, customer data APIs, internal databases — on behalf of an organization.

**Problem without AIS:** The agent uses a shared API key or a borrowed user account. When something goes wrong, there is no clear record of which agent made which call, or whether it was authorized to do so.

**With AIS:** The agent presents a signed `agent+jwt` to the API gateway or service. The gateway verifies the assertion offline (no live issuer call), extracts the agent's `org_id`, `team_id`, `framework`, and `environment` claims, and applies access policy. The request is attributable to a specific, named agent.

---

## API gateway enforcement

**Scenario:** An organization runs an API gateway in front of its services. All AI agents from across the organization route traffic through it.

**With AIS:** The gateway is configured as a verifier. It:
1. Fetches and caches the issuer JWKS
2. Validates the `agent+jwt` on each incoming request
3. Enforces policy (e.g., production agents only, approved frameworks only)
4. Logs the `agent_id`, `team_id`, and `environment` for every request

No changes are needed to the upstream services — enforcement happens at the gateway.

---

## Cross-system agent trust

**Scenario:** An agent issued by Platform A needs to call a service managed by Platform B. Both platforms are operated by the same organization but use different infrastructure.

**With AIS:** Platform B operates a verifier. It discovers Platform A's issuer metadata from `/.well-known/agent-issuer`, fetches its JWKS, and verifies the agent's assertion. No shared secrets or platform-specific integration is needed.

This is the same model OIDC enables for cross-system user identity — one standard that multiple systems can independently verify.

---

## Audit and compliance

**Scenario:** A compliance team needs to demonstrate that AI agents only accessed systems they were authorized to access, and that every action is attributable to a specific agent identity.

**With AIS:** Every agent request carries a verifiable assertion. Control planes can log the `agent_id`, `jti`, `framework`, `environment`, and action for every request. The audit trail is agent-attributable rather than just IP- or key-attributable.

For frameworks that include AIS alongside an audit control plane (like ACP), the audit log can be hash-chained for tamper-evidence and exported for compliance reporting.

---

## Enterprise policy enforcement

**Scenario:** An enterprise has different risk tolerances for different agent types. Production agents should require approval for high-risk actions. Development agents should not be able to write to production databases.

**With AIS:** Policy is expressed in terms of the verified claims in the agent assertion:
- `environment: production` → require approval for model calls above a certain cost threshold
- `environment: development` → deny any action targeting a production resource
- `framework: langgraph` + `attestation_level: runtime_verified` → allow sensitive operations

Policy is enforced at the control plane level, not embedded in individual agents.

---

## Multi-agent systems

**Scenario:** A multi-agent system has orchestrator and worker agents. The orchestrator delegates tasks to workers, and the workers call external services. Each call needs to be attributable to the right agent.

**With AIS:** Each agent — orchestrator and workers — has its own identity credential. When a worker calls an external service, it presents its own `agent+jwt`. The service can verify which agent made the call, not just which orchestrator authorized it.

Delegation chain semantics (tracking the path from orchestrator to worker) are a planned extension.

---

## Framework and platform interoperability

**Scenario:** An organization uses LangGraph for some agents and CrewAI for others. Both types of agents need to call the same internal services.

**With AIS:** Both frameworks issue `agent+jwt` assertions via an AIS-conformant issuer. Verifiers do not need to understand LangGraph or CrewAI — they just verify the assertion. The `framework` claim is available if policy needs to distinguish agent types.
