"""Policy DSL parser — YAML surface syntax → compiled policy dict (POL-01)."""
from __future__ import annotations

import re
from typing import Any

import yaml

# Valid action types (POL-06)
VALID_ACTION_TYPES = {
    "api_call",
    "database_operation",
    "filesystem_access",
    "tool_invocation",
    "llm_call",
    "agent_delegation",
}

VALID_OUTCOMES = {"allow", "deny", "require_approval"}

VALID_DB_OPERATIONS = {"SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"}


class PolicyDSLError(ValueError):
    pass


def parse_and_compile(dsl_source: str) -> dict[str, Any]:
    """Parse YAML DSL and return a compiled policy dict.

    Raises PolicyDSLError with a human-readable message on invalid syntax.
    """
    try:
        raw = yaml.safe_load(dsl_source)
    except yaml.YAMLError as exc:
        raise PolicyDSLError(f"Invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise PolicyDSLError("Policy must be a YAML mapping at the top level")

    _require(raw, "policy_id", str)
    _require(raw, "outcome", str)

    outcome = raw["outcome"]
    if outcome not in VALID_OUTCOMES:
        raise PolicyDSLError(
            f"Invalid outcome '{outcome}'. Must be one of: {', '.join(sorted(VALID_OUTCOMES))}"
        )

    # Subject
    subject = raw.get("subject", {})
    if not isinstance(subject, dict):
        raise PolicyDSLError("'subject' must be a mapping")

    # Action
    action = raw.get("action", {})
    if not isinstance(action, dict):
        raise PolicyDSLError("'action' must be a mapping")
    if "type" in action and action["type"] not in VALID_ACTION_TYPES:
        raise PolicyDSLError(
            f"Unknown action type '{action['type']}'. Valid: {', '.join(sorted(VALID_ACTION_TYPES))}"
        )
    if action.get("type") == "database_operation":
        ops = action.get("operations", [])
        bad = [o for o in ops if o not in VALID_DB_OPERATIONS]
        if bad:
            raise PolicyDSLError(f"Unknown database operations: {bad}")

    # Resource
    resource = raw.get("resource", {})
    if not isinstance(resource, dict):
        raise PolicyDSLError("'resource' must be a mapping")

    # Approval config (required when outcome == require_approval)
    approval_config = raw.get("approval_config", {})
    if outcome == "require_approval":
        if not approval_config:
            raise PolicyDSLError(
                "'approval_config' is required when outcome is 'require_approval'"
            )

    # Alert config
    alert = raw.get("alert", {})

    conditions = raw.get("conditions", {})
    if not isinstance(conditions, dict):
        raise PolicyDSLError("'conditions' must be a mapping")
    if "attestation" in conditions and not isinstance(conditions["attestation"], dict):
        raise PolicyDSLError("'conditions.attestation' must be a mapping")

    compiled = {
        "policy_id": raw["policy_id"],
        "description": raw.get("description", ""),
        "outcome": outcome,
        "subject": subject,
        "action": action,
        "resource": resource,
        "conditions": conditions,
        "approval_config": approval_config,
        "alert": alert,
    }
    return compiled


def _require(d: dict, key: str, type_: type) -> None:
    if key not in d:
        raise PolicyDSLError(f"Missing required field: '{key}'")
    if not isinstance(d[key], type_):
        raise PolicyDSLError(
            f"Field '{key}' must be a {type_.__name__}, got {type(d[key]).__name__}"
        )
