"""Typed result types for AIS verification."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AgentClaims:
    """Decoded and verified claims from an AIS agent+jwt.

    All standard AIS claims are surfaced as typed attributes.
    The full raw payload is available via `.raw`.
    """

    agent_id: str
    org_id: str
    team_id: str
    framework: str
    environment: str
    issuer: str
    subject: str
    issued_at: int
    expires_at: int
    jti: str
    display_name: Optional[str] = None
    audience: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict, compare=False)

    @classmethod
    def from_payload(cls, payload: dict) -> AgentClaims:
        aud = payload.get("aud", [])
        if isinstance(aud, str):
            aud = [aud]
        return cls(
            agent_id=payload["agent_id"],
            org_id=payload["org_id"],
            team_id=payload["team_id"],
            framework=payload["framework"],
            environment=payload["environment"],
            issuer=payload["iss"],
            subject=payload["sub"],
            issued_at=payload["iat"],
            expires_at=payload["exp"],
            jti=payload["jti"],
            display_name=payload.get("display_name"),
            audience=aud,
            raw=dict(payload),
        )


@dataclass(frozen=True)
class IssuerMetadata:
    """Parsed AIS issuer discovery document (/.well-known/agent-issuer)."""

    issuer: str
    jwks_uri: str
    spec_version: str
    agent_registration_endpoint: str
    agent_attestation_endpoint: str
    supported_assertion_types: list[str]
    supported_signing_alg_values: list[str]
    supported_framework_values: list[str] = field(default_factory=list)
    supported_environment_values: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict, compare=False)

    @classmethod
    def from_dict(cls, d: dict) -> IssuerMetadata:
        return cls(
            issuer=d["issuer"],
            jwks_uri=d["jwks_uri"],
            spec_version=d.get("spec_version", ""),
            agent_registration_endpoint=d.get("agent_registration_endpoint", ""),
            agent_attestation_endpoint=d.get("agent_attestation_endpoint", ""),
            supported_assertion_types=d.get("supported_assertion_types", ["agent+jwt"]),
            supported_signing_alg_values=d.get("supported_signing_alg_values", ["RS256"]),
            supported_framework_values=d.get("supported_framework_values", []),
            supported_environment_values=d.get("supported_environment_values", []),
            raw=dict(d),
        )
