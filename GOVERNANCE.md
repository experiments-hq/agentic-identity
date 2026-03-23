# Governance

## Current Status

AIS is currently maintained by a small group of contributors under the `experiments-hq` GitHub organization. This is a bootstrapping arrangement, not a permanent governance model.

## Intended Direction

The goal for AIS is to move governance to a neutral standards body. This repository is a staging ground for the protocol, not a proprietary product claim.

We are actively interested in contributing AIS to one of the following:

- **IETF** — potentially under the OAuth or GNAP working groups, or as an independent submission
- **Linux Foundation** — as part of an AI trust or agent identity working group
- **NIST** — as input to the AI Risk Management Framework or related AI standards initiatives
- **OpenID Foundation** — as a profile or extension of existing identity standards

The decision about which path to pursue will depend on where meaningful community engagement forms and which body provides the right technical scope for agent identity.

## Principles

**The spec is the contribution.** The protocol design, token format, attestation model, and conformance requirements are intended to be freely adoptable by any implementer. No part of the AIS specification is intended to create vendor lock-in.

**Governance transfer is a goal, not a threat.** If a standards body or foundation wants to take stewardship of this protocol, that is the intended outcome. We will support that transition rather than resist it.

**The reference implementation (ACP) and the SDK are separate from the spec.** Downstream control-plane products and enterprise implementations can be built on top of AIS without any obligation to use these specific components.

## How to Engage on Governance

If you represent a standards body, foundation, or working group interested in this protocol, open a GitHub issue with the `governance` label or contact us directly at experiments-hq@outlook.com.

If you are an identity practitioner, IETF participant, or NIST contributor with opinions on how agent identity should be standardized, we want to hear from you. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to engage on the specification itself.
