"""ACP Proxy Interceptor — the central enforcement point.

Every LLM API call passes through here:
  1. Authenticate agent JWT
  2. Check policy (allow / deny / require_approval)
  3. Check budget hard-stop
  4. Forward to upstream LLM provider
  5. Record trace span + budget usage
  6. Write audit event
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from acp.config import settings
from acp.primitives.audit.logger import EventType, log_event
from acp.primitives.budget.tracker import check_budget, record_usage
from acp.primitives.identity.service import authenticate_request
from acp.primitives.observability.tracer import estimate_cost
from acp.primitives.policy.engine import ActionRequest, policy_engine
from acp.models.trace import AgentTrace, TraceSpan

log = logging.getLogger(__name__)

# Upstream base URLs keyed by path prefix
_UPSTREAM_MAP: dict[str, str] = {
    "/anthropic/": settings.anthropic_base_url,
    "/openai/":    settings.openai_base_url,
    # Default: treat bare /v1/* as Anthropic
    "/v1/":        settings.anthropic_base_url,
}


def _detect_upstream(path: str) -> tuple[str, str]:
    """Return (upstream_base_url, stripped_path).

    Agents can call ACP at:
      /anthropic/v1/messages  → https://api.anthropic.com/v1/messages
      /openai/v1/chat/completions → https://api.openai.com/v1/chat/completions
      /v1/messages            → https://api.anthropic.com/v1/messages  (default)
    """
    for prefix, base in _UPSTREAM_MAP.items():
        if path.startswith(prefix):
            # Strip the vendor prefix but keep /v1/...
            stripped = path[len(prefix) - len("/v1/"):]  # keep /v1/ onwards
            if not stripped.startswith("/"):
                stripped = "/" + stripped
            return base, stripped
    raise HTTPException(status_code=404, detail=f"Unknown proxy path: {path}")


def _extract_model_id(body: dict) -> str:
    return body.get("model", "unknown")


def _extract_token_usage(response_body: dict) -> tuple[int, int]:
    """Try to extract (input_tokens, output_tokens) from LLM provider response."""
    usage = response_body.get("usage", {})
    # Anthropic
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    # OpenAI
    if not inp:
        inp = usage.get("prompt_tokens", 0)
    if not out:
        out = usage.get("completion_tokens", 0)
    return inp, out


async def handle_proxy_request(request: Request, db: AsyncSession) -> Response:
    """Main proxy handler — called for every /v1/* and /anthropic/*, /openai/* request."""

    request_id = str(uuid.uuid4())
    source_ip = request.client.host if request.client else None
    path = request.url.path

    # ── 1. Extract bearer token ───────────────────────────────────────────────
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    bearer_token = auth_header[len("Bearer "):]

    # ── 2. Authenticate ───────────────────────────────────────────────────────
    try:
        agent_payload = await authenticate_request(db, bearer_token)
    except ValueError as exc:
        await log_event(
            db,
            event_type=EventType.LLM_CALL_BLOCKED,
            actor_type="agent",
            actor_id="unknown",
            resource_type="llm_api",
            resource_id=path,
            action="proxy_request",
            outcome="failure",
            payload={"reason": str(exc), "path": path},
            source_ip=source_ip,
            request_id=request_id,
        )
        raise HTTPException(status_code=401, detail=str(exc))

    agent_id   = agent_payload["agent_id"]
    org_id     = agent_payload["org_id"]
    team_id    = agent_payload["team_id"]
    environment = agent_payload["environment"]
    framework  = agent_payload.get("framework", "custom")

    # ── 3. Read and parse request body ───────────────────────────────────────
    raw_body = await request.body()
    try:
        body = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        body = {}

    model_id = _extract_model_id(body)

    # ── 4. Policy evaluation ──────────────────────────────────────────────────
    # Determine trace_id from header (allows multi-agent traces)
    trace_id = request.headers.get("x-acp-trace-id") or str(uuid.uuid4())

    action_req = ActionRequest(
        agent_id=agent_id,
        org_id=org_id,
        team_id=team_id,
        environment=environment,
        action_type="llm_call",
        action_detail={
            "model_id": model_id,
            "path": path,
            "method": request.method,
        },
        resource={"environment": environment},
        trace_id=trace_id,
    )

    decision = await policy_engine.evaluate(db, action_req)

    if decision.decision == "deny":
        await log_event(
            db,
            event_type=EventType.POLICY_VIOLATION,
            actor_type="agent",
            actor_id=agent_id,
            resource_type="llm_api",
            resource_id=model_id,
            action="llm_call",
            outcome="blocked",
            payload={
                "policy_id": decision.policy_id,
                "reason": decision.reason,
                "model_id": model_id,
                "org_id": org_id,
            },
            source_ip=source_ip,
            request_id=request_id,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "policy_violation",
                "policy_id": decision.policy_id,
                "reason": decision.reason,
            },
        )

    if decision.decision == "require_approval":
        from acp.primitives.approvals.engine import (
            create_approval_request,
            wait_for_decision,
        )
        approval = await create_approval_request(
            db,
            agent_id=agent_id,
            trace_id=trace_id,
            policy_id=decision.policy_id or "unknown",
            action_type="llm_call",
            action_detail={"model_id": model_id, "path": path},
            approval_config=decision.approval_config,
        )
        await db.commit()  # persist so approvers can see it

        final = await wait_for_decision(db, approval.request_id)

        if final.status != "approved":
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "approval_denied",
                    "request_id": approval.request_id,
                    "status": final.status,
                    "reason": final.decision_reason,
                },
            )

    # ── 5. Budget check ───────────────────────────────────────────────────────
    allowed, budget_reason = await check_budget(db, org_id=org_id, team_id=team_id, agent_id=agent_id)
    if not allowed:
        await log_event(
            db,
            event_type=EventType.LLM_CALL_BLOCKED,
            actor_type="agent",
            actor_id=agent_id,
            resource_type="budget",
            resource_id=agent_id,
            action="llm_call",
            outcome="blocked",
            payload={"reason": budget_reason, "model_id": model_id, "org_id": org_id},
            source_ip=source_ip,
            request_id=request_id,
        )
        raise HTTPException(status_code=429, detail={"error": "budget_exceeded", "reason": budget_reason})

    # ── 6. Forward to upstream ────────────────────────────────────────────────
    upstream_base, upstream_path = _detect_upstream(path)
    upstream_url = f"{upstream_base}{upstream_path}"

    # Pass-through headers — strip ACP auth, keep upstream auth
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "authorization", "x-acp-trace-id")
    }
    # The agent must supply their LLM API key in x-acp-upstream-auth or
    # via the standard x-api-key / Authorization headers after stripping.
    upstream_auth = request.headers.get("x-acp-upstream-auth", "")
    if upstream_auth:
        if upstream_base == settings.anthropic_base_url:
            forward_headers["x-api-key"] = upstream_auth
        else:
            forward_headers["authorization"] = f"Bearer {upstream_auth}"

    span_started = datetime.now(tz=timezone.utc)
    t0 = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            upstream_resp = await client.request(
                method=request.method,
                url=upstream_url,
                headers=forward_headers,
                content=raw_body,
                params=dict(request.query_params),
            )
    except httpx.RequestError as exc:
        log.error("Upstream request failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream error: {exc}")

    elapsed_ms = (time.monotonic() - t0) * 1000
    span_ended = datetime.now(tz=timezone.utc)

    # ── 7. Parse response for usage data ─────────────────────────────────────
    input_tokens, output_tokens = 0, 0
    cost_usd = 0.0
    try:
        resp_body = upstream_resp.json()
        input_tokens, output_tokens = _extract_token_usage(resp_body)
        cost_usd = estimate_cost(model_id, input_tokens, output_tokens)
    except Exception:
        pass

    # ── 8. Record trace span ──────────────────────────────────────────────────
    # Ensure a trace row exists (idempotent: multiple proxy calls share same trace)
    from sqlalchemy import select
    existing = await db.execute(
        select(AgentTrace).where(AgentTrace.trace_id == trace_id)
    )
    if not existing.scalar_one_or_none():
        trace_row = AgentTrace(
            trace_id=trace_id,
            agent_id=agent_id,
            org_id=org_id,
            team_id=team_id,
            started_at=span_started,
            framework=framework,
            environment=environment,
        )
        db.add(trace_row)
        await db.flush()

    span = TraceSpan(
        span_id=str(uuid.uuid4()),
        trace_id=trace_id,
        span_type="llm_call",
        name=f"{request.method} {upstream_path}",
        started_at=span_started,
        ended_at=span_ended,
        duration_ms=elapsed_ms,
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        inputs={"path": path, "model": model_id} if not settings.pii_redaction_enabled else {},
        outputs={"status": upstream_resp.status_code},
        policy_decision=decision.decision,
        policy_id=decision.policy_id,
        status="ok" if upstream_resp.status_code < 400 else "error",
        error=str(upstream_resp.status_code) if upstream_resp.status_code >= 400 else None,
    )
    db.add(span)

    # ── 9. Record budget usage ────────────────────────────────────────────────
    if input_tokens or output_tokens:
        await record_usage(
            db,
            org_id=org_id,
            team_id=team_id,
            agent_id=agent_id,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

    # ── 10. Audit event ───────────────────────────────────────────────────────
    await log_event(
        db,
        event_type=EventType.LLM_CALL_ALLOWED,
        actor_type="agent",
        actor_id=agent_id,
        resource_type="llm_api",
        resource_id=model_id,
        action="llm_call",
        outcome="success" if upstream_resp.status_code < 400 else "failure",
        payload={
            "model_id": model_id,
            "path": path,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "upstream_status": upstream_resp.status_code,
            "policy_id": decision.policy_id,
            "trace_id": trace_id,
            "org_id": org_id,
        },
        source_ip=source_ip,
        request_id=request_id,
    )

    # ── 11. Return upstream response verbatim ─────────────────────────────────
    excluded_headers = {"content-encoding", "transfer-encoding", "content-length"}
    response_headers = {
        k: v for k, v in upstream_resp.headers.items()
        if k.lower() not in excluded_headers
    }
    response_headers["x-acp-trace-id"] = trace_id
    response_headers["x-acp-request-id"] = request_id

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=response_headers,
        media_type=upstream_resp.headers.get("content-type", "application/json"),
    )
