# Examples

Runnable examples showing how AIS works in practice.

---

## gateway_enforcement.py

**The core AIS claim made concrete:** two agents share the same org and upstream API key, but the gateway distinguishes them by their individual signed identities and applies different policy to each.

```bash
# Requires a running ACP server with demo data
acp serve &
acp demo-seed
python examples/gateway_enforcement.py
```

This directly demonstrates the scenario described in the AIS design rationale: policy enforcement on per-agent identity rather than on the underlying workload credential.

---

## Planned examples

### Verifier integrations
- Verifying an `agent+jwt` in a FastAPI endpoint
- Verifying an `agent+jwt` in an Express / Node.js middleware
- Verifying an `agent+jwt` in a Go HTTP handler

### Issuer examples
- Minimal AIS-conformant issuer in Python
- Issuer metadata discovery endpoint

### Gateway integrations
- Kong plugin for agent assertion validation
- Envoy external authorization filter
- AWS API Gateway Lambda authorizer

### Framework adapters
- LangGraph agent with AIS identity
- CrewAI agent with AIS identity

---

## Contributing examples

If you have built an integration with AIS, we welcome contributions. See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the process.

Examples should:
- be self-contained and runnable
- include a short README explaining the integration
- demonstrate a real use case, not just API calls
