"""AgentVerifier — reusable AIS token verifier with JWKS caching."""
from __future__ import annotations

import asyncio
from typing import Optional

from ._discover import JWKSCache, fetch_issuer_metadata, fetch_jwks
from ._jwt import decode_and_verify
from .exceptions import AISVerificationError
from .types import AgentClaims, IssuerMetadata


class AgentVerifier:
    """Verify AIS agent+jwt tokens offline against a published JWKS.

    JWKS documents are cached (default 5 minutes) so repeated calls to
    ``verify()`` do not incur a network round-trip on every token.

    Usage — with issuer discovery::

        verifier = AgentVerifier(issuer="https://acp.example.com")
        claims = await verifier.verify(token)
        print(claims.agent_id, claims.environment)

    Usage — offline with an explicit JWKS dict::

        verifier = AgentVerifier(jwks={"keys": [...]})
        claims = await verifier.verify(token)

    Usage — sync environments::

        verifier = AgentVerifier(issuer="https://acp.example.com")
        claims = verifier.verify_sync(token)
    """

    def __init__(
        self,
        *,
        issuer: Optional[str] = None,
        jwks: Optional[dict] = None,
        audience: Optional[str] = None,
        jwks_cache_ttl: float = 300.0,
    ) -> None:
        if issuer is None and jwks is None:
            raise ValueError("Provide either 'issuer' (for discovery) or 'jwks' (for offline verification)")
        self._issuer = issuer
        self._static_jwks = jwks
        self._audience = audience
        self._cache = JWKSCache(ttl=jwks_cache_ttl)
        self._metadata: Optional[IssuerMetadata] = None

    async def discover(self) -> IssuerMetadata:
        """Fetch and cache issuer metadata.

        Called lazily on the first ``verify()`` when constructed with an
        ``issuer`` URL. Safe to call directly if you want the metadata object.
        """
        if self._metadata is not None:
            return self._metadata
        if self._issuer is None:
            raise ValueError("Issuer URL required for discovery")
        raw = await fetch_issuer_metadata(self._issuer)
        self._metadata = IssuerMetadata.from_dict(raw)
        return self._metadata

    async def _get_jwks(self) -> dict:
        if self._static_jwks is not None:
            return self._static_jwks
        meta = await self.discover()
        return await fetch_jwks(meta.jwks_uri, cache=self._cache)

    async def verify(
        self,
        token: str,
        *,
        audience: Optional[str] = None,
        required_environment: Optional[str] = None,
        required_framework: Optional[str] = None,
    ) -> AgentClaims:
        """Verify an agent+jwt and return typed identity claims.

        Args:
            token: Raw JWT string (``eyJ...``).
            audience: Expected ``aud`` value. Overrides the constructor default.
            required_environment: Reject tokens whose ``environment`` claim
                does not match this value (e.g. ``"production"``).
            required_framework: Reject tokens whose ``framework`` claim does
                not match this value (e.g. ``"langgraph"``).

        Returns:
            :class:`AgentClaims` with all standard AIS fields typed.

        Raises:
            :exc:`InvalidSignatureError`: RSA signature does not verify.
            :exc:`TokenExpiredError`: Token has passed its ``exp`` timestamp.
            :exc:`MissingClaimError`: A required AIS claim is absent.
            :exc:`AISVerificationError`: Other verification failure.
            :exc:`IssuerDiscoveryError`: Could not reach the issuer metadata endpoint.
            :exc:`JWKSError`: Could not fetch or parse the JWKS document.
        """
        jwks = await self._get_jwks()
        aud = audience or self._audience
        payload = decode_and_verify(token, jwks, audience=aud)
        claims = AgentClaims.from_payload(payload)

        if required_environment and claims.environment != required_environment:
            raise AISVerificationError(
                f"Environment mismatch: token carries '{claims.environment}', "
                f"policy requires '{required_environment}'"
            )
        if required_framework and claims.framework != required_framework:
            raise AISVerificationError(
                f"Framework mismatch: token carries '{claims.framework}', "
                f"policy requires '{required_framework}'"
            )

        return claims

    def verify_sync(self, token: str, **kwargs) -> AgentClaims:
        """Synchronous wrapper around :meth:`verify`.

        Suitable for non-async contexts (scripts, Django views, etc.).
        Creates a new event loop for each call — use the async API in hot paths.
        """
        return asyncio.run(self.verify(token, **kwargs))
