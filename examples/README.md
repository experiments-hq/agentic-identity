# Examples

This directory will contain runnable integration examples for AIS.

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
