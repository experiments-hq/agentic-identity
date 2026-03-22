# Contributing to AIS

Thank you for your interest in contributing to the Agent Identity Specification.

---

## What You Can Contribute

- **Bug reports** — errors in the specification, incorrect examples, broken code
- **Clarifications** — ambiguous normative language, missing edge cases
- **Implementation feedback** — if you implement AIS and discover the spec is unclear or underspecified
- **Specification proposals** — new claims, new protocol flows, new conformance requirements
- **Reference implementation improvements** — the ACP server and ais-verify SDK
- **Examples** — additional example documents, integration patterns

---

## Reporting Issues

Open a GitHub issue. For specification issues, please include:

- the section of the spec that is affected
- the current text
- what the problem is
- proposed resolution (optional)

For code bugs, include the steps to reproduce and the actual vs. expected behavior.

---

## Submitting Pull Requests

1. Fork the repository and create a branch from `main`.
2. Make your changes.
3. Open a pull request with a clear description of what changed and why.

Keep pull requests focused. One logical change per PR.

---

## Spec Changes

Changes to normative specification text (`ais/SPEC.md`, `ais/ATTESTATION.md`, `ais/CONFORMANCE.md`) require more discussion than code changes.

For non-trivial spec changes, open an issue first to discuss the proposal before writing a PR. This avoids wasted effort if the change is out of scope or conflicts with existing design decisions.

The design constraints and rationale for existing decisions are documented in [RATIONALE.md](./RATIONALE.md). Proposals that conflict with those decisions should explain why the trade-off should be reconsidered.

**RFC 2119 keywords** (`MUST`, `SHOULD`, `MAY`) in the specification carry their standard meanings per [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119). Changes that promote a `SHOULD` to a `MUST` or demote a `MUST` to a `SHOULD` are normative changes and require explicit justification.

---

## Development Setup

```bash
git clone https://github.com/nokoro27/agent-identity.git
cd agent-identity

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run the ACP reference server
python -m acp.main

# Run the protocol demo (self-contained, no server needed)
python demo.py
```

---

## Code Style

- Python 3.11+
- `from __future__ import annotations` at the top of all Python files
- Type annotations on all function signatures
- No external formatting tools are enforced; follow the style of the surrounding code

---

## JSON Schema

Changes to `ais/schema/agent-identity.schema.json` that add new required fields are breaking changes. New optional fields are non-breaking. Any schema change should be accompanied by updated examples in `ais/examples/`.

---

## Versioning

AIS follows [Semantic Versioning](https://semver.org/) for specification versions:

- **Patch** (`0.1.x`): clarifications, example fixes, non-normative changes
- **Minor** (`0.x.0`): new optional features, new SHOULD-level requirements
- **Major** (`x.0.0`): breaking changes to required fields, endpoints, or token format

The current version is `0.1-draft`. Until `1.0`, breaking changes may occur in minor versions with clear changelog entries.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
