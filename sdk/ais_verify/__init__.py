"""ais-verify — standalone SDK for verifying AIS agent+jwt tokens.

Verify any AIS-issued agent assertion offline — no ACP server required,
no governance stack, just the token and a JWKS.

Quickstart::

    from ais_verify import AgentVerifier

    verifier = AgentVerifier(issuer="https://acp.example.com")
    claims = await verifier.verify(token)
    print(claims.agent_id, claims.environment)

One-shot helper::

    from ais_verify import verify_agent_jwt

    claims = await verify_agent_jwt(token, issuer="https://acp.example.com")

Sync environments::

    from ais_verify import verify_agent_jwt_sync

    claims = verify_agent_jwt_sync(token, issuer="https://acp.example.com")

Offline (no network calls)::

    verifier = AgentVerifier(jwks={"keys": [...]})
    claims = await verifier.verify(token)
"""
from __future__ import annotations

import asyncio
from typing import Optional

from ._discover import fetch_issuer_metadata
from .exceptions import (
    AISVerificationError,
    IssuerDiscoveryError,
    InvalidSignatureError,
    JWKSError,
    MissingClaimError,
    TokenExpiredError,
)
from .types import AgentClaims, IssuerMetadata
from .verifier import AgentVerifier


async def verify_agent_jwt(
    token: str,
    *,
    issuer: Optional[str] = None,
    jwks: Optional[dict] = None,
    audience: Optional[str] = None,
) -> AgentClaims:
    """One-shot convenience function for verifying an agent+jwt.

    Args:
        token: The raw JWT string.
        issuer: Issuer base URL for discovery. Mutually exclusive with ``jwks``.
        jwks: JWKS dict for offline verification. Mutually exclusive with ``issuer``.
        audience: Expected ``aud`` claim value.

    Returns:
        :class:`AgentClaims` with all standard AIS fields typed.

    Example::

        claims = await verify_agent_jwt(
            token,
            issuer="https://acp.example.com",
        )
        print(claims.agent_id)    # "5f8d9f32-..."
        print(claims.framework)   # "langgraph"
    """
    verifier = AgentVerifier(issuer=issuer, jwks=jwks, audience=audience)
    return await verifier.verify(token)


def verify_agent_jwt_sync(
    token: str,
    *,
    issuer: Optional[str] = None,
    jwks: Optional[dict] = None,
    audience: Optional[str] = None,
) -> AgentClaims:
    """Sync wrapper around :func:`verify_agent_jwt`.

    Creates a new event loop per call — prefer the async API in hot paths.
    """
    return asyncio.run(
        verify_agent_jwt(token, issuer=issuer, jwks=jwks, audience=audience)
    )


__all__ = [
    "AgentVerifier",
    "AgentClaims",
    "IssuerMetadata",
    "verify_agent_jwt",
    "verify_agent_jwt_sync",
    "fetch_issuer_metadata",
    "AISVerificationError",
    "TokenExpiredError",
    "InvalidSignatureError",
    "MissingClaimError",
    "IssuerDiscoveryError",
    "JWKSError",
]

__version__ = "0.1.0"
