# Demo

This directory contains end-to-end demonstration assets for AIS and ACP.

---

## demo.py — in-process protocol walkthrough

`demo/demo.py` walks the complete AIS flow in a single process with no server required. It is the fastest way to see the protocol in action.

```bash
# From the repo root — no server needed
python demo/demo.py

# Or against a running ACP server
python demo/demo.py --url http://localhost:8000
```

What it demonstrates:

1. Issuer discovery — `GET /.well-known/agent-issuer`
2. JWKS retrieval — `GET /.well-known/jwks.json`
3. Agent registration — `POST /api/agents/register` → returns a signed `agent+jwt`
4. Offline JWT verification — decodes and verifies the token without a network call
5. Attestation challenge — `POST /v1/attestations/challenge`
6. Attestation response — `POST /v1/attestations` (JWT signature verified against nonce)

---

## Live agent simulation

For a full governance stack demo against a running ACP server:

```bash
# First, start the server and seed demo data
pip install -e .
acp serve &
acp demo-seed

# Then run the live simulation
python -m acp.demo_agent
```

This simulates an agent going through all 11 governance steps:
- identity registration
- attestation
- policy simulation (allow, require_approval, deny)
- credential rotation
- audit log verification
- fleet registry lookup

The ACP governance console is available at `http://localhost:8000/console/`.

---

## Prerequisites

```bash
pip install -e ".[dev]"
```

Python 3.11 or later is required.
