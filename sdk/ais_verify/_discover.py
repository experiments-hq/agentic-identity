"""AIS issuer discovery and JWKS fetching with TTL cache."""
from __future__ import annotations

import time
from typing import Optional

import httpx

from .exceptions import IssuerDiscoveryError, JWKSError


class JWKSCache:
    """Simple in-memory TTL cache for JWKS documents."""

    def __init__(self, ttl: float = 300.0) -> None:
        self._store: dict[str, tuple[dict, float]] = {}
        self._ttl = ttl

    def get(self, url: str) -> Optional[dict]:
        entry = self._store.get(url)
        if entry is not None:
            data, expires = entry
            if time.monotonic() < expires:
                return data
            del self._store[url]
        return None

    def set(self, url: str, data: dict) -> None:
        self._store[url] = (data, time.monotonic() + self._ttl)

    def invalidate(self, url: str) -> None:
        self._store.pop(url, None)


# Module-level default cache shared across AgentVerifier instances
_default_cache = JWKSCache()


async def fetch_issuer_metadata(
    issuer: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """Fetch and return the AIS issuer metadata document.

    Requests ``{issuer}/.well-known/agent-issuer``.

    Raises:
        IssuerDiscoveryError: Network failure or non-200 response.
    """
    url = issuer.rstrip("/") + "/.well-known/agent-issuer"
    try:
        if client is not None:
            r = await client.get(url)
        else:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(url)
        r.raise_for_status()
        return r.json()
    except IssuerDiscoveryError:
        raise
    except Exception as exc:
        raise IssuerDiscoveryError(
            f"Failed to fetch issuer metadata from {url}: {exc}"
        ) from exc


async def fetch_jwks(
    jwks_uri: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
    cache: Optional[JWKSCache] = None,
) -> dict:
    """Fetch the JWKS document, returning a cached copy if still valid.

    Raises:
        JWKSError: Network failure or invalid JWKS response.
    """
    store = cache if cache is not None else _default_cache
    cached = store.get(jwks_uri)
    if cached is not None:
        return cached

    try:
        if client is not None:
            r = await client.get(jwks_uri)
        else:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(jwks_uri)
        r.raise_for_status()
        jwks = r.json()
    except JWKSError:
        raise
    except Exception as exc:
        raise JWKSError(f"Failed to fetch JWKS from {jwks_uri}: {exc}") from exc

    if "keys" not in jwks:
        raise JWKSError(f"JWKS response from {jwks_uri} is missing 'keys' field")

    store.set(jwks_uri, jwks)
    return jwks
