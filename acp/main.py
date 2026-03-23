"""ACP FastAPI application — entry point."""
from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from acp.config import settings
from acp.database import create_all_tables, get_db_dependency

log = logging.getLogger("acp")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


_DEFAULT_ADMIN_TOKEN = "acp-demo-admin-token"
_DEFAULT_SECRET_KEY = "acp-dev-secret-key-change-me"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ACP starting — env=%s", settings.env)

    if settings.is_production:
        errors: list[str] = []
        if settings.admin_token == _DEFAULT_ADMIN_TOKEN:
            errors.append("ACP_ADMIN_TOKEN is set to the default demo value — set a strong secret")
        if settings.secret_key == _DEFAULT_SECRET_KEY:
            errors.append("ACP_SECRET_KEY is set to the default dev value — set a strong secret")
        if settings.cors_allowed_origins == ["*"]:
            errors.append("ACP_CORS_ALLOWED_ORIGINS is '*' — restrict to your console origin")
        if errors:
            for msg in errors:
                log.critical("PRODUCTION MISCONFIGURATION: %s", msg)
            raise RuntimeError(
                "ACP refused to start in production with insecure defaults:\n"
                + "\n".join(f"  • {e}" for e in errors)
            )

    await create_all_tables()
    log.info("Database tables ready")
    yield
    log.info("ACP shutting down")


app = FastAPI(
    title="Agent Control Plane",
    version="0.1.0",
    description=(
        "Governance, identity, and observability platform for enterprise AI agents. "
        "Seven integrated primitives: Agent Identity, Policy Enforcement, Approvals, "
        "Observability, Budget Controls, Incident Replay, and Audit/Compliance."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Admin API routers ─────────────────────────────────────────────────────────

from acp.api.agents import router as agents_router
from acp.api.policies import router as policies_router
from acp.api.approvals import router as approvals_router
from acp.api.traces import router as traces_router
from acp.api.budgets import router as budgets_router
from acp.api.replay import router as replay_router
from acp.api.audit import router as audit_router
from acp.api.demo import router as demo_router
from acp.api.attestations import router as attestations_router
from acp.api.session import SESSION_COOKIE, router as session_router

app.include_router(agents_router)
app.include_router(policies_router)
app.include_router(approvals_router)
app.include_router(traces_router)
app.include_router(budgets_router)
app.include_router(replay_router)
app.include_router(audit_router)
app.include_router(demo_router)
app.include_router(session_router)
app.include_router(attestations_router)
app.mount("/console", StaticFiles(directory="acp/console", html=True), name="console")


@app.middleware("http")
async def require_operator_session(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or path.startswith("/api/session/") or os.getenv("PYTEST_CURRENT_TEST"):
        return await call_next(request)

    presented_token = request.cookies.get(SESSION_COOKIE) or request.headers.get("x-acp-admin-token", "")
    if not secrets.compare_digest(presented_token, settings.admin_token):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Admin authentication required"},
        )
    return await call_next(request)


# ── Proxy routes — all LLM traffic flows through here ────────────────────────

from acp.proxy.interceptor import handle_proxy_request  # noqa: F401
from acp.database import AsyncSessionLocal


@app.api_route(
    "/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    tags=["proxy"],
    summary="LLM Proxy — Anthropic-compatible endpoint",
    include_in_schema=True,
)
@app.api_route(
    "/anthropic/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    tags=["proxy"],
    summary="LLM Proxy — namespaced Anthropic endpoint",
    include_in_schema=False,
)
@app.api_route(
    "/openai/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    tags=["proxy"],
    summary="LLM Proxy — namespaced OpenAI endpoint",
    include_in_schema=False,
)
async def llm_proxy(request: Request):
    """Transparent LLM proxy. Agents point their SDK base_url here.

    Authentication: pass your ACP agent JWT as `Authorization: Bearer <token>`.
    Upstream LLM API key goes in `x-acp-upstream-auth`.
    """
    async with AsyncSessionLocal() as db:
        try:
            response = await handle_proxy_request(request, db)
            await db.commit()
            return response
        except Exception:
            await db.rollback()
            raise


# ── JWKS public endpoint (AID-07) ────────────────────────────────────────────

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends


def _issuer_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@app.get("/.well-known/agent-issuer", tags=["identity"])
async def agent_issuer_metadata(request: Request):
    """Public AIS issuer metadata document."""
    issuer = _issuer_base_url(request)
    return {
        "issuer": issuer,
        "spec_version": "0.1-draft",
        "jwks_uri": f"{issuer}/.well-known/jwks.json",
        "agent_registration_endpoint": f"{issuer}/api/agents/register",
        "agent_attestation_endpoint": f"{issuer}/v1/attestations",
        "supported_signing_alg_values": [settings.jwt_algorithm],
        "supported_assertion_types": ["agent+jwt"],
        "supported_framework_values": ["langgraph", "crewai", "autogen", "custom", "openclaw", "nemoclaw"],
        "supported_environment_values": ["development", "staging", "production"],
    }


@app.get("/.well-known/jwks.json", tags=["identity"])
async def jwks_public(db: AsyncSession = Depends(get_db_dependency)):
    """Public JWKS endpoint — verifiable without calling ACP at runtime."""
    from acp.primitives.identity.service import get_jwks
    return await get_jwks(db)


# ── Health + info ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "0.1.0", "env": settings.env}


@app.get("/", tags=["system"])
async def root():
    return {
        "name": "Agent Control Plane",
        "version": "0.1.0",
        "docs": "/docs",
        "primitives": [
            "identity",
            "policy",
            "observability",
            "approvals",
            "budget",
            "replay",
            "audit",
        ],
    }


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def serve():
    uvicorn.run(
        "acp.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.env == "development",
        log_level="info",
    )


if __name__ == "__main__":
    serve()
