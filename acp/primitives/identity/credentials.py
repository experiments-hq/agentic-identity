"""RSA key management and JWT credential lifecycle (AID-02, AID-03, AID-04, AID-07)."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from acp.config import settings


# ── Key encryption helpers (AES-256-GCM) ─────────────────────────────────────

def _derive_key() -> bytes:
    """Derive a 32-byte AES key from ACP_SECRET_KEY."""
    return hashlib.sha256(settings.secret_key.encode()).digest()


def encrypt_private_key(private_key_pem: bytes) -> str:
    """Encrypt a PEM private key with AES-256-GCM; return base64-encoded ciphertext."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, private_key_pem, None)
    payload = nonce + ct
    return base64.b64encode(payload).decode()


def decrypt_private_key(encrypted: str) -> bytes:
    """Decrypt and return PEM private key bytes."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    payload = base64.b64decode(encrypted)
    nonce, ct = payload[:12], payload[12:]
    return aesgcm.decrypt(nonce, ct, None)


# ── RSA key generation ────────────────────────────────────────────────────────

def generate_rsa_key_pair() -> tuple[str, str, str]:
    """Generate an RSA key pair.

    Returns:
        (key_id, public_key_pem_str, encrypted_private_key_str)
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=settings.rsa_key_size,
    )
    public_key = private_key.public_key()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Deterministic key_id from public key fingerprint
    key_id = hashlib.sha256(public_pem).hexdigest()[:16]
    encrypted = encrypt_private_key(private_pem)
    return key_id, public_pem.decode(), encrypted


# ── JWT creation ──────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_agent_jwt(
    *,
    agent_id: str,
    org_id: str,
    team_id: str,
    framework: str,
    environment: str,
    key_id: str,
    private_key_encrypted: str,
    expiry_hours: Optional[int] = None,
) -> tuple[str, str, datetime]:
    """Sign and return a JWT for an agent.

    Returns:
        (jwt_string, jti, expires_at_datetime)
    """
    now = int(time.time())
    jti = str(uuid.uuid4())
    exp_hours = expiry_hours or settings.jwt_default_expiry_hours
    exp = now + exp_hours * 3600
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

    header = {"alg": "RS256", "typ": "agent+jwt", "kid": key_id}
    payload = {
        "sub": agent_id,
        "agent_id": agent_id,
        "org_id": org_id,
        "team_id": team_id,
        "framework": framework,
        "environment": environment,
        "iat": now,
        "exp": exp,
        "jti": jti,
        "iss": "acp",
    }

    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    private_pem = decrypt_private_key(private_key_encrypted)
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    private_key = load_pem_private_key(private_pem, password=None)

    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = _b64url(signature)

    token = f"{header_b64}.{payload_b64}.{sig_b64}"
    return token, jti, expires_at


# ── JWT verification ──────────────────────────────────────────────────────────

def verify_agent_jwt(
    token: str,
    public_key_pem: str,
) -> dict:
    """Verify signature and expiry; return decoded payload dict.

    Raises ValueError on any failure.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed JWT: expected 3 parts")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode()

    # Decode payload
    payload_json = base64.urlsafe_b64decode(_pad(payload_b64))
    payload = json.loads(payload_json)

    # Check expiry
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("JWT expired")

    # Verify signature
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    public_key = load_pem_public_key(public_key_pem.encode())
    signature = base64.urlsafe_b64decode(_pad(sig_b64))

    try:
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except Exception as exc:
        raise ValueError(f"JWT signature invalid: {exc}") from exc

    return payload


def _pad(b64: str) -> str:
    return b64 + "=" * (-len(b64) % 4)


# ── JWKS helpers ──────────────────────────────────────────────────────────────

def public_key_to_jwk(key_id: str, public_key_pem: str) -> dict:
    """Convert a PEM public key to a JWK object (RSA, RS256)."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

    pub_key: RSAPublicKey = load_pem_public_key(public_key_pem.encode())
    pub_numbers = pub_key.public_key().public_numbers() if hasattr(pub_key, "public_key") else pub_key.public_numbers()

    def _int_to_b64(n: int) -> str:
        length = (n.bit_length() + 7) // 8
        return _b64url(n.to_bytes(length, "big"))

    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": key_id,
        "n": _int_to_b64(pub_numbers.n),
        "e": _int_to_b64(pub_numbers.e),
    }
