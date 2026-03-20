# Agent Control Plane

Agent Control Plane (ACP) is a governance, identity, and observability platform for enterprise AI agents.

This repository currently contains:
- the ACP application and console in [`acp/`](c:/Users/nenye/acp/acp)
- a draft Agent Identity Specification in [`ais/`](c:/Users/nenye/acp/ais)

## Agent Identity Specification

AIS is intended to play a role for AI agents that is similar to what OpenID Connect did for user identity:
- a standard identity model for agents
- signed credentials that can be verified offline
- issuer discovery metadata
- JWKS-based key distribution
- a portable attestation flow for proving agent properties at runtime

See:
- [ais/README.md](c:/Users/nenye/acp/ais/README.md)
- [ais/SPEC.md](c:/Users/nenye/acp/ais/SPEC.md)
- [ais/ATTESTATION.md](c:/Users/nenye/acp/ais/ATTESTATION.md)
