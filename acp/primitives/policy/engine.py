"""Policy Enforcement Engine — real-time allow/deny/require_approval (POL-01…POL-08)."""
from __future__ import annotations

import fnmatch
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acp.config import settings
from acp.models.policy import Policy, PolicyDecisionLog


# ── Decision result ───────────────────────────────────────────────────────────

class PolicyDecision:
    __slots__ = ("decision", "policy_id", "reason", "approval_config", "evaluation_ms")

    def __init__(
        self,
        decision: str,
        policy_id: Optional[str],
        reason: str,
        approval_config: Optional[dict] = None,
        evaluation_ms: float = 0.0,
    ) -> None:
        self.decision = decision          # allow | deny | require_approval
        self.policy_id = policy_id
        self.reason = reason
        self.approval_config = approval_config or {}
        self.evaluation_ms = evaluation_ms

    @property
    def is_allowed(self) -> bool:
        return self.decision == "allow"

    @property
    def requires_approval(self) -> bool:
        return self.decision == "require_approval"


# ── Action request ────────────────────────────────────────────────────────────

class ActionRequest:
    """Describes an agent action to be evaluated against policies."""

    def __init__(
        self,
        *,
        agent_id: str,
        org_id: str,
        team_id: str,
        environment: str,
        action_type: str,
        action_detail: dict[str, Any],
        resource: Optional[dict[str, Any]] = None,
        attestation: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.agent_id = agent_id
        self.org_id = org_id
        self.team_id = team_id
        self.environment = environment
        self.action_type = action_type
        self.action_detail = action_detail
        self.resource = resource or {}
        self.attestation = attestation or {}
        self.trace_id = trace_id
        self.timestamp = datetime.now(tz=timezone.utc)


# ── Core evaluator ────────────────────────────────────────────────────────────

def _match_subject(subject: dict, req: ActionRequest) -> bool:
    """Return True if the policy subject matches this request."""
    if not subject:
        return True  # wildcard subject

    # agent_id match
    if "agent_id" in subject:
        if subject["agent_id"] != req.agent_id:
            return False

    # team_id match
    if "team_id" in subject:
        if subject["team_id"] != req.team_id:
            return False

    # org_id match
    if "org_id" in subject:
        if subject["org_id"] != req.org_id:
            return False

    # environment match
    if "agent_environment" in subject:
        if subject["agent_environment"] != req.environment:
            return False

    return True


def _match_action(action: dict, req: ActionRequest) -> bool:
    """Return True if the policy action spec matches this request."""
    if not action:
        return True

    if "type" in action and action["type"] != req.action_type:
        return False

    # endpoint_pattern for api_call
    if req.action_type == "api_call" and "endpoint_pattern" in action:
        endpoint = req.action_detail.get("endpoint", "")
        if not fnmatch.fnmatch(endpoint, action["endpoint_pattern"].replace("*", "**")):
            # Also try plain glob
            pattern = action["endpoint_pattern"]
            if not _glob_match(endpoint, pattern):
                return False

    # operations for database_operation
    if req.action_type == "database_operation" and "operations" in action:
        op = req.action_detail.get("operation", "").upper()
        if op not in [o.upper() for o in action["operations"]]:
            return False

    # tool_id for tool_invocation
    if req.action_type == "tool_invocation" and "tool_id" in action:
        if req.action_detail.get("tool_id") != action["tool_id"]:
            return False

    # model_id for llm_call
    if req.action_type == "llm_call" and "model_id" in action:
        if req.action_detail.get("model_id") != action["model_id"]:
            return False

    return True


def _match_resource(resource: dict, req: ActionRequest) -> bool:
    """Return True if the policy resource spec matches the request's resource."""
    if not resource:
        return True

    res = req.resource

    if "environment" in resource:
        if res.get("environment") != resource["environment"]:
            return False

    if "data_classification" in resource:
        req_classes = res.get("data_classification", [])
        policy_classes = resource["data_classification"]
        # At least one classification must match
        if not any(c in req_classes for c in policy_classes):
            return False

    return True


def _match_conditions(conditions: dict, req: ActionRequest) -> bool:
    """Evaluate optional conditions (time window, etc.)."""
    if not conditions:
        return True

    # time_window: {"days": ["monday",...], "hours": "09:00-17:00"}
    if "time_window" in conditions:
        tw = conditions["time_window"]
        now = req.timestamp
        if "days" in tw:
            day_name = now.strftime("%A").lower()
            if day_name not in [d.lower() for d in tw["days"]]:
                return False
        if "hours" in tw:
            start_str, end_str = tw["hours"].split("-")
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
            current_minutes = now.hour * 60 + now.minute
            start_minutes = sh * 60 + sm
            end_minutes = eh * 60 + em
            if not (start_minutes <= current_minutes <= end_minutes):
                return False

    # attestation: require specific verified posture claims
    if "attestation" in conditions:
        attestation = conditions["attestation"]
        if not isinstance(attestation, dict):
            return False

        if "verified" in attestation:
            if bool(req.attestation.get("verified")) != bool(attestation["verified"]):
                return False

        claims = req.attestation.get("claims", {})
        if not isinstance(claims, dict):
            claims = {}

        for key, expected in attestation.get("claims", {}).items():
            if claims.get(key) != expected:
                return False

        required = attestation.get("required_claims", [])
        if any(claim not in claims for claim in required):
            return False

    return True


def _specificity(policy: Policy) -> int:
    """Higher = more specific. Agent > team > org."""
    return {"agent": 3, "team": 2, "org": 1}.get(policy.scope_level, 0)


def _glob_match(text: str, pattern: str) -> bool:
    regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return bool(re.fullmatch(regex, text))


# ── Engine ────────────────────────────────────────────────────────────────────

class PolicyEngine:
    """Stateless policy evaluation engine. Instantiate once, reuse per request."""

    async def evaluate(
        self,
        db: AsyncSession,
        req: ActionRequest,
    ) -> PolicyDecision:
        """Evaluate all applicable policies and return a decision.

        Policy priority order: agent-scoped > team-scoped > org-scoped.
        First matching policy at the highest specificity wins.
        Default: deny (POL-03).
        """
        t0 = time.monotonic()

        # Load active policies for this org
        result = await db.execute(
            select(Policy).where(
                Policy.org_id == req.org_id,
                Policy.is_active == True,  # noqa: E712
            )
        )
        policies: list[Policy] = list(result.scalars().all())

        # Sort by specificity (most specific first)
        policies.sort(key=_specificity, reverse=True)

        matched_policy: Optional[Policy] = None
        for policy in policies:
            compiled = policy.compiled

            # Subject scope check
            if policy.scope_level == "agent" and policy.scope_id != req.agent_id:
                continue
            if policy.scope_level == "team" and policy.scope_id != req.team_id:
                continue
            if policy.scope_level == "org" and policy.scope_id != req.org_id:
                continue

            # DSL matching
            if not _match_subject(compiled.get("subject", {}), req):
                continue
            if not _match_action(compiled.get("action", {}), req):
                continue
            if not _match_resource(compiled.get("resource", {}), req):
                continue
            if not _match_conditions(compiled.get("conditions", {}), req):
                continue

            matched_policy = policy
            break

        elapsed_ms = (time.monotonic() - t0) * 1000

        if matched_policy is None:
            decision = PolicyDecision(
                decision=settings.policy_default_action,
                policy_id=None,
                reason="No matching policy — default action applied",
                evaluation_ms=elapsed_ms,
            )
        else:
            outcome = matched_policy.compiled["outcome"]
            approval_config = matched_policy.compiled.get("approval_config", {})
            decision = PolicyDecision(
                decision=outcome,
                policy_id=matched_policy.policy_id,
                reason=f"Matched policy: {matched_policy.policy_id}",
                approval_config=approval_config,
                evaluation_ms=elapsed_ms,
            )

        # Persist decision log
        log_entry = PolicyDecisionLog(
            agent_id=req.agent_id,
            trace_id=req.trace_id,
            action_type=req.action_type,
            action_detail=req.action_detail,
            matched_policy_id=decision.policy_id,
            decision=decision.decision,
            decision_reason=decision.reason,
            evaluation_ms=elapsed_ms,
        )
        db.add(log_entry)
        # Note: caller is responsible for committing the session.

        return decision

    async def simulate(
        self,
        db: AsyncSession,
        req: ActionRequest,
    ) -> PolicyDecision:
        """Same as evaluate() but does NOT write to the decision log (POL-07)."""
        # Temporarily monkey-patch to skip DB write — or just re-implement without log write.
        t0 = time.monotonic()

        result = await db.execute(
            select(Policy).where(
                Policy.org_id == req.org_id,
                Policy.is_active == True,  # noqa: E712
            )
        )
        policies = list(result.scalars().all())
        policies.sort(key=_specificity, reverse=True)

        for policy in policies:
            compiled = policy.compiled
            if policy.scope_level == "agent" and policy.scope_id != req.agent_id:
                continue
            if policy.scope_level == "team" and policy.scope_id != req.team_id:
                continue
            if policy.scope_level == "org" and policy.scope_id != req.org_id:
                continue
            if not _match_subject(compiled.get("subject", {}), req):
                continue
            if not _match_action(compiled.get("action", {}), req):
                continue
            if not _match_resource(compiled.get("resource", {}), req):
                continue
            if not _match_conditions(compiled.get("conditions", {}), req):
                continue

            elapsed_ms = (time.monotonic() - t0) * 1000
            return PolicyDecision(
                decision=compiled["outcome"],
                policy_id=policy.policy_id,
                reason=f"Matched policy: {policy.policy_id}",
                approval_config=compiled.get("approval_config", {}),
                evaluation_ms=elapsed_ms,
            )

        elapsed_ms = (time.monotonic() - t0) * 1000
        return PolicyDecision(
            decision=settings.policy_default_action,
            policy_id=None,
            reason="No matching policy — default action applied",
            evaluation_ms=elapsed_ms,
        )


# Module-level singleton
policy_engine = PolicyEngine()
