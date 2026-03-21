"""JWT decoding and RSA-SHA256 signature verification for agent+jwt tokens."""
from __future__ import annotations

import base64
import json
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

from .exceptions import InvalidSignatureError, MissingClaimError, TokenExpiredError

# All claims required by the AIS spec (CONFORMANCE.md §4)
_REQUIRED_CLAIMS = frozenset({
    "iss", "sub", "iat", "exp", "jti",
    "agent_id", "org_id", "team_id", "framework", "environment",
})


def _b64url_decode(s: str) -> bytes:
    padded = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(padded)


def _b64url_to_int(s: str) -> int:
    return int.from_bytes(_b64url_decode(s), "big")


def _build_public_key(jwk: dict):
    """Reconstruct an RSA public key from a JWKS key entry."""
    if jwk.get("kty") != "RSA":
        raise ValueError(f"Unsupported key type: {jwk.get('kty')!r}")
    n = _b64url_to_int(jwk["n"])
    e = _b64url_to_int(jwk["e"])
    return RSAPublicNumbers(e, n).public_key()


def decode_and_verify(
    token: str,
    jwks: dict,
    *,
    audience: Optional[str] = None,
    allow_expired: bool = False,
) -> dict:
    """Decode and cryptographically verify an agent+jwt.

    Args:
        token: Raw JWT string.
        jwks: JWKS document dict ({"keys": [...]}).
        audience: If provided, the token's ``aud`` claim must include this value.
        allow_expired: Skip expiry check (useful for testing / replay analysis).

    Returns:
        Decoded payload dict.

    Raises:
        ValueError: Malformed token, unsupported algorithm, or wrong token type.
        InvalidSignatureError: RSA signature invalid or key not found.
        TokenExpiredError: Token has passed its ``exp`` timestamp.
        MissingClaimError: A required AIS claim is absent.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(f"Malformed JWT: expected 3 parts, got {len(parts)}")

    header_b64, payload_b64, sig_b64 = parts

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise ValueError(f"Failed to decode JWT header/payload: {exc}") from exc

    # --- Header validation ---
    alg = header.get("alg")
    if alg != "RS256":
        raise ValueError(f"Unsupported algorithm: {alg!r}. AIS requires RS256.")

    typ = header.get("typ")
    if typ != "agent+jwt":
        raise ValueError(f"Invalid token type: {typ!r}. Expected 'agent+jwt'.")

    kid = header.get("kid")
    if not kid:
        raise ValueError("JWT header is missing 'kid'")

    # --- Find matching JWKS key ---
    keys = jwks.get("keys", [])
    matching = [k for k in keys if k.get("kid") == kid]
    if not matching:
        raise InvalidSignatureError(
            f"No key in JWKS matches kid={kid!r}. "
            f"Available kids: {[k.get('kid') for k in keys]}"
        )

    try:
        public_key = _build_public_key(matching[0])
    except Exception as exc:
        raise InvalidSignatureError(f"Failed to build public key from JWKS: {exc}") from exc

    # --- Verify RSA-SHA256 signature ---
    message = f"{header_b64}.{payload_b64}".encode("ascii")
    try:
        signature = _b64url_decode(sig_b64)
    except Exception as exc:
        raise InvalidSignatureError(f"Failed to decode signature: {exc}") from exc

    try:
        public_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
    except Exception as exc:
        raise InvalidSignatureError(f"Signature verification failed: {exc}") from exc

    # --- Expiry check ---
    exp = payload.get("exp")
    if exp is None:
        raise MissingClaimError("Token is missing required claim 'exp'")
    if not allow_expired and time.time() > exp:
        raise TokenExpiredError(
            f"Token expired at {exp} (current time: {time.time():.0f}). "
            "Request a new credential."
        )

    # --- Required AIS claims ---
    for claim in _REQUIRED_CLAIMS:
        if claim not in payload:
            raise MissingClaimError(f"Token is missing required AIS claim: '{claim}'")

    # --- Audience check ---
    if audience is not None:
        aud = payload.get("aud", [])
        if isinstance(aud, str):
            aud = [aud]
        if audience not in aud:
            raise ValueError(
                f"Audience mismatch: expected {audience!r}, got {aud!r}"
            )

    return payload
