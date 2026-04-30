# ais-verify

Standalone verifier SDK for [Agent Identity Specification (AIS)](../spec/SPEC.md) `agent+jwt` tokens.

Verify any AIS-issued agent assertion offline — no ACP server required, no governance stack, just the token and a JWKS.

```
OpenID Connect  →  PyJWT / python-jose  →  verify ID tokens
AIS             →  ais-verify           →  verify agent+jwt tokens
```

## Install

```bash
pip install ais-verify
```

## Quickstart

```python
from ais_verify import AgentVerifier

verifier = AgentVerifier(issuer="https://acp.example.com")
claims = await verifier.verify(token)

print(claims.agent_id)     # "5f8d9f32-..."
print(claims.org_id)       # "org-acme"
print(claims.framework)    # "langgraph"
print(claims.environment)  # "production"
```

## One-shot helper

```python
from ais_verify import verify_agent_jwt

claims = await verify_agent_jwt(token, issuer="https://acp.example.com")
```

## Offline (no network calls)

Pass the JWKS dict directly — verifier never touches the network:

```python
verifier = AgentVerifier(jwks={"keys": [...]})
claims = await verifier.verify(token)
```

## Sync environments

```python
from ais_verify import verify_agent_jwt_sync

claims = verify_agent_jwt_sync(token, issuer="https://acp.example.com")
```

## Policy enforcement

Reject tokens that don't meet your requirements:

```python
claims = await verifier.verify(
    token,
    required_environment="production",
    required_framework="langgraph",
)
```

## Reusable verifier (recommended for hot paths)

The `AgentVerifier` caches the JWKS for 5 minutes by default, so
repeated calls don't refetch on every token:

```python
# Create once, reuse across requests
verifier = AgentVerifier(issuer="https://acp.example.com")

async def handle_agent_request(request):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    claims = await verifier.verify(token, required_environment="production")
    return process(claims)
```

## Error handling

```python
from ais_verify import (
    InvalidSignatureError,
    TokenExpiredError,
    MissingClaimError,
    IssuerDiscoveryError,
)

try:
    claims = await verifier.verify(token)
except TokenExpiredError:
    # token has passed exp — request a new credential
    ...
except InvalidSignatureError:
    # RSA signature did not verify against JWKS
    ...
except MissingClaimError as e:
    # required AIS claim is absent
    print(e)
except IssuerDiscoveryError:
    # couldn't reach /.well-known/agent-issuer
    ...
```

## What it verifies

1. JWT is well-formed with three parts
2. `alg` is `RS256` and `typ` is `agent+jwt`
3. `kid` matches a key published in the issuer's JWKS
4. RSA-SHA256 signature is valid
5. Token has not passed `exp`
6. All required AIS claims are present: `iss`, `sub`, `iat`, `exp`, `jti`, `agent_id`, `org_id`, `team_id`, `framework`, `environment`
7. Optional: `aud` matches, `environment` matches, `framework` matches

## AgentClaims fields

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | Stable unique agent identifier |
| `org_id` | `str` | Owning organization |
| `team_id` | `str` | Owning team |
| `framework` | `str` | Declared execution framework |
| `environment` | `str` | `development`, `staging`, or `production` |
| `issuer` | `str` | Issuer URL (`iss`) |
| `subject` | `str` | Same as `agent_id` (`sub`) |
| `issued_at` | `int` | Unix timestamp |
| `expires_at` | `int` | Unix timestamp |
| `jti` | `str` | Unique token identifier |
| `display_name` | `str \| None` | Human-readable agent label |
| `audience` | `list[str]` | Intended audiences |
| `raw` | `dict` | Full decoded payload |

## Dependencies

- [`cryptography`](https://cryptography.io/) — RSA signature verification
- [`httpx`](https://www.python-httpx.org/) — JWKS and issuer metadata fetching

No FastAPI. No SQLAlchemy. No database. No governance layer.

## Related

- [AIS Specification](../spec/SPEC.md)
- [AIS Conformance Requirements](../spec/CONFORMANCE.md)
- [Agent Control Plane (ACP)](../acp/) — full reference implementation with governance
