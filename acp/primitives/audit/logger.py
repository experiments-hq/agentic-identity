"""Audit logger — immutable, cryptographically chained event log (AUD-01…AUD-03, AUD-06)."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from acp.models.audit import AuditEvent

# Genesis hash — first entry's previous_hash
_GENESIS_HASH = "0" * 64


# ── Event types ───────────────────────────────────────────────────────────────
class EventType:
    # Identity
    AGENT_REGISTERED = "agent.registered"
    AGENT_SUSPENDED = "agent.suspended"
    AGENT_REVOKED = "agent.revoked"
    CREDENTIAL_ISSUED = "credential.issued"
    CREDENTIAL_ROTATED = "credential.rotated"
    CREDENTIAL_REVOKED = "credential.revoked"

    # Policy
    POLICY_CREATED = "policy.created"
    POLICY_UPDATED = "policy.updated"
    POLICY_ROLLED_BACK = "policy.rolled_back"
    POLICY_VIOLATION = "policy.violation"

    # Approvals
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_DENIED = "approval.denied"
    APPROVAL_TIMED_OUT = "approval.timed_out"
    APPROVAL_ESCALATED = "approval.escalated"

    # Budget
    BUDGET_CREATED = "budget.created"
    BUDGET_THRESHOLD_ALERT = "budget.threshold_alert"
    BUDGET_HARD_STOP = "budget.hard_stop"

    # Proxy / LLM calls
    LLM_CALL_BLOCKED = "llm_call.blocked"
    LLM_CALL_ALLOWED = "llm_call.allowed"

    # Admin
    ADMIN_LOGIN = "admin.login"
    ADMIN_ACTION = "admin.action"


def _compute_hash(previous_hash: str, event_id: str, event_type: str, timestamp: str, payload: dict) -> str:
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    content = f"{previous_hash}|{event_id}|{event_type}|{timestamp}|{payload_str}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def _get_last_hash(db: AsyncSession) -> str:
    result = await db.execute(
        select(AuditEvent.event_hash).order_by(AuditEvent.id.desc()).limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row else _GENESIS_HASH


async def log_event(
    db: AsyncSession,
    *,
    event_type: str,
    actor_type: str,
    actor_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    outcome: str,
    payload: dict,
    source_ip: Optional[str] = None,
    request_id: Optional[str] = None,
) -> AuditEvent:
    """Append an immutable event to the audit log with hash-chain integrity."""
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")

    previous_hash = await _get_last_hash(db)
    event_hash = _compute_hash(previous_hash, event_id, event_type, timestamp, payload)

    event = AuditEvent(
        event_id=event_id,
        event_type=event_type,
        timestamp=timestamp,
        actor_type=actor_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        outcome=outcome,
        source_ip=source_ip,
        request_id=request_id,
        payload=payload,
        event_hash=event_hash,
        previous_hash=previous_hash,
    )
    db.add(event)
    await db.flush()
    return event


# ── Chain verification (AUD-06) ───────────────────────────────────────────────

async def verify_chain(db: AsyncSession) -> tuple[bool, Optional[str]]:
    """Recompute hash chain and detect any tampering.

    Returns (is_valid, first_tampered_event_id_or_None).
    """
    result = await db.execute(
        select(AuditEvent).order_by(AuditEvent.id)
    )
    events = result.scalars().all()

    expected_previous = _GENESIS_HASH
    for event in events:
        if event.previous_hash != expected_previous:
            return False, event.event_id

        expected_hash = _compute_hash(
            event.previous_hash,
            event.event_id,
            event.event_type,
            event.timestamp,
            event.payload,
        )
        if event.event_hash != expected_hash:
            return False, event.event_id

        expected_previous = event.event_hash

    return True, None
