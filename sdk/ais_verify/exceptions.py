"""AIS verification exceptions."""


class AISVerificationError(Exception):
    """Base class for all AIS verification errors."""


class TokenExpiredError(AISVerificationError):
    """Token has passed its expiry time."""


class InvalidSignatureError(AISVerificationError):
    """JWT signature does not match the JWKS key."""


class MissingClaimError(AISVerificationError):
    """A required AIS claim is absent from the token."""


class IssuerDiscoveryError(AISVerificationError):
    """Failed to fetch or parse issuer metadata."""


class JWKSError(AISVerificationError):
    """Failed to fetch or parse the JWKS document."""
