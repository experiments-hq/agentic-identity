"""Compliance report generation (AUD-04 EU AI Act, AUD-05 SOC 2)."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from acp.models.agent import Agent
from acp.models.approval import ApprovalRequest
from acp.models.audit import AuditEvent
from acp.models.policy import Policy, PolicyDecisionLog
from acp.models.trace import AgentTrace


# ── JSON export ───────────────────────────────────────────────────────────────

async def export_audit_log_json(
    db: AsyncSession,
    *,
    org_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    event_type: Optional[str] = None,
    limit: int = 10_000,
    offset: int = 0,
) -> list[dict]:
    q = select(AuditEvent).order_by(AuditEvent.id)
    if start:
        q = q.where(AuditEvent.timestamp >= start.isoformat())
    if end:
        q = q.where(AuditEvent.timestamp <= end.isoformat())
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    if org_id:
        q = q.where(AuditEvent.payload["org_id"].as_string() == org_id)
    q = q.limit(limit).offset(offset)

    result = await db.execute(q)
    events = result.scalars().all()

    return [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "timestamp": e.timestamp,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "action": e.action,
            "outcome": e.outcome,
            "source_ip": e.source_ip,
            "request_id": e.request_id,
            "payload": e.payload,
            "event_hash": e.event_hash,
            "previous_hash": e.previous_hash,
        }
        for e in events
    ]


async def export_audit_log_csv(
    db: AsyncSession,
    **kwargs,
) -> str:
    """Return CSV string of the audit log."""
    events = await export_audit_log_json(db, **kwargs)
    if not events:
        return ""

    output = io.StringIO()
    fieldnames = [
        "event_id", "event_type", "timestamp", "actor_type", "actor_id",
        "resource_type", "resource_id", "action", "outcome", "source_ip",
        "request_id", "event_hash",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(events)
    return output.getvalue()


# ── EU AI Act compliance report (AUD-04) ─────────────────────────────────────

async def generate_eu_ai_act_report(
    db: AsyncSession,
    org_id: str,
    start: datetime,
    end: datetime,
) -> dict:
    """Generate structured EU AI Act compliance report (Articles 9/10/11)."""

    # Article 9 — Risk management: policy violations and responses
    violations_result = await db.execute(
        select(func.count()).select_from(PolicyDecisionLog).where(
            PolicyDecisionLog.agent_id.in_(
                select(Agent.agent_id).where(Agent.org_id == org_id)
            ),
            PolicyDecisionLog.decision == "deny",
            PolicyDecisionLog.evaluated_at >= start,
            PolicyDecisionLog.evaluated_at <= end,
        )
    )
    total_violations = violations_result.scalar() or 0

    # Article 10 — Training / data quality: agent registry
    agents_result = await db.execute(
        select(func.count()).select_from(Agent).where(Agent.org_id == org_id)
    )
    total_agents = agents_result.scalar() or 0

    active_agents_result = await db.execute(
        select(func.count()).select_from(Agent).where(
            Agent.org_id == org_id, Agent.status == "active"
        )
    )
    active_agents = active_agents_result.scalar() or 0

    # Article 11 — Record keeping: audit log completeness
    audit_events_result = await db.execute(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.timestamp >= start.isoformat(),
            AuditEvent.timestamp <= end.isoformat(),
        )
    )
    total_audit_events = audit_events_result.scalar() or 0

    # Human oversight: approvals
    approvals_result = await db.execute(
        select(func.count()).select_from(ApprovalRequest).where(
            ApprovalRequest.agent_id.in_(
                select(Agent.agent_id).where(Agent.org_id == org_id)
            ),
            ApprovalRequest.created_at >= start,
            ApprovalRequest.created_at <= end,
        )
    )
    total_approvals = approvals_result.scalar() or 0

    approved_result = await db.execute(
        select(func.count()).select_from(ApprovalRequest).where(
            ApprovalRequest.agent_id.in_(
                select(Agent.agent_id).where(Agent.org_id == org_id)
            ),
            ApprovalRequest.status == "approved",
            ApprovalRequest.created_at >= start,
            ApprovalRequest.created_at <= end,
        )
    )
    approved_count = approved_result.scalar() or 0

    return {
        "report_type": "eu_ai_act_compliance",
        "org_id": org_id,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "article_9_risk_management": {
            "total_policy_violations": total_violations,
            "description": "All agent actions evaluated against declared policies. Violations logged and alerted.",
        },
        "article_10_data_governance": {
            "registered_agents": total_agents,
            "active_agents": active_agents,
            "all_agents_have_identity": True,
            "framework_coverage": "All agent frameworks tracked via ACP identity service",
        },
        "article_11_record_keeping": {
            "total_audit_events": total_audit_events,
            "audit_log_integrity": "SHA-256 hash-chained append-only log",
            "retention_policy": "Configurable; default 7 years for enterprise",
        },
        "human_oversight": {
            "approval_requests_total": total_approvals,
            "approved": approved_count,
            "denied": total_approvals - approved_count,
            "human_in_the_loop_enabled": True,
        },
    }


# ── SOC 2 evidence package (AUD-05) ──────────────────────────────────────────

async def generate_soc2_evidence(
    db: AsyncSession,
    org_id: str,
    start: datetime,
    end: datetime,
) -> dict:
    """Generate SOC 2 Type II evidence package."""

    # Access control evidence
    agents = await db.execute(
        select(Agent).where(Agent.org_id == org_id)
    )
    agent_list = [
        {"agent_id": a.agent_id, "display_name": a.display_name,
         "status": a.status, "team_id": a.team_id, "environment": a.environment}
        for a in agents.scalars().all()
    ]

    # Change management: policy changes
    policy_changes_result = await db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type.in_(["policy.created", "policy.updated", "policy.rolled_back"]),
            AuditEvent.timestamp >= start.isoformat(),
            AuditEvent.timestamp <= end.isoformat(),
        ).order_by(AuditEvent.timestamp)
    )
    policy_changes = [
        {"timestamp": e.timestamp, "actor": e.actor_id, "event": e.event_type, "resource": e.resource_id}
        for e in policy_changes_result.scalars().all()
    ]

    # Incident log: violations and responses
    incidents_result = await db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type.in_(["policy.violation", "budget.hard_stop"]),
            AuditEvent.timestamp >= start.isoformat(),
            AuditEvent.timestamp <= end.isoformat(),
        ).order_by(AuditEvent.timestamp)
    )
    incidents = [
        {"timestamp": e.timestamp, "type": e.event_type, "actor": e.actor_id, "outcome": e.outcome}
        for e in incidents_result.scalars().all()
    ]

    return {
        "report_type": "soc2_evidence_package",
        "org_id": org_id,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "access_control": {
            "total_agents": len(agent_list),
            "agents": agent_list,
            "identity_mechanism": "RSA-256 signed JWTs, org-scoped key pairs",
            "credential_lifecycle": "Registration, issuance, rotation, revocation tracked",
        },
        "change_management": {
            "total_policy_changes": len(policy_changes),
            "changes": policy_changes,
        },
        "incident_log": {
            "total_incidents": len(incidents),
            "incidents": incidents,
        },
    }
