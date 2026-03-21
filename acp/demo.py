"""Shared demo seeding utilities for CLI and console-triggered scenarios."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, text

DEMO_ORG_ID = "00000000-0000-0000-0000-00000000demo"
DEMO_ACTOR = "console-demo"
DEMO_POLICY_IDS = [
    "allow-attested-sonnet-in-prod",
    "deny-dev-prod-db-writes",
    "require-approval-for-opus-payments",
]
DEMO_TRACE_IDS = [
    "44444444-4444-4444-4444-444444444441",
    "44444444-4444-4444-4444-444444444442",
    "44444444-4444-4444-4444-444444444443",
    "44444444-4444-4444-4444-444444444444",
]
DEMO_APPROVAL_IDS = [
    "55555555-5555-5555-5555-555555555551",
    "55555555-5555-5555-5555-555555555552",
]
DEMO_BUDGET_ID = "bb000000-0000-0000-0000-00000000demo"
DEMO_AGENTS = [
    {
        "agent_id": "11111111-1111-1111-1111-111111111111",
        "team_id": "team-finance-001",
        "display_name": "Finance Ops Agent",
        "framework": "langgraph",
        "environment": "production",
        "tags": {"tier": "critical", "owner": "platform"},
    },
    {
        "agent_id": "22222222-2222-2222-2222-222222222222",
        "team_id": "team-support-001",
        "display_name": "Support Triage Agent",
        "framework": "crewai",
        "environment": "staging",
        "tags": {"tier": "core", "owner": "support"},
    },
    {
        "agent_id": "33333333-3333-3333-3333-333333333333",
        "team_id": "team-rnd-001",
        "display_name": "Research Sandbox Agent",
        "framework": "custom",
        "environment": "development",
        "tags": {"tier": "experimental", "owner": "ai-lab"},
    },
    {
        "agent_id": "44444444-aaaa-bbbb-cccc-shadow000001",
        "team_id": "team-unknown",
        "display_name": "Shadow Billing Agent",
        "framework": "custom",
        "environment": "production",
        "tags": {"tier": "unregistered", "owner": "unknown", "shadow": "true", "detected_by": "ais-fleet-scan"},
    },
]
DEMO_POLICY_SPECS = [
    {
        "scope_level": "org",
        "scope_id": DEMO_ORG_ID,
        "dsl_source": """
policy_id: "allow-attested-sonnet-in-prod"
description: "Allow Claude Sonnet in production only when runtime posture is attested"
subject:
  org_id: "00000000-0000-0000-0000-00000000demo"
action:
  type: llm_call
  model_id: claude-sonnet-4-6
resource:
  environment: production
conditions:
  attestation:
    verified: true
    claims:
      runtime_class: cloud_run
      build_digest: sha256:demo-build
    required_claims: [runtime_class, build_digest]
outcome: allow
""".strip(),
    },
    {
        "scope_level": "org",
        "scope_id": DEMO_ORG_ID,
        "dsl_source": """
policy_id: "deny-dev-prod-db-writes"
description: "Block development agents from writing into production systems"
subject:
  agent_environment: development
action:
  type: database_operation
  operations: [INSERT, UPDATE, DELETE, DROP]
resource:
  environment: production
outcome: deny
alert:
  severity: critical
  channels: [slack#security-alerts]
""".strip(),
    },
    {
        "scope_level": "org",
        "scope_id": DEMO_ORG_ID,
        "dsl_source": """
policy_id: "require-approval-for-opus-payments"
description: "Escalate expensive payment-impacting model calls for human approval"
subject:
  org_id: "00000000-0000-0000-0000-00000000demo"
action:
  type: llm_call
  model_id: claude-opus-4-6
resource:
  environment: production
outcome: require_approval
approval_config:
  timeout_minutes: 30
  channels: [slack#security-alerts]
""".strip(),
    },
]


async def seed_demo_data(db, *, replace_existing: bool = True) -> dict[str, int]:
    from acp.models.agent import Agent, AgentCredential, RSAKeyPair
    from acp.models.approval import ApprovalDecision, ApprovalRequest
    from acp.models.audit import AuditEvent
    from acp.models.budget import BudgetLimit, BudgetUsage  # noqa: F811
    from acp.models.policy import Policy, PolicyDecisionLog, PolicyVersion
    from acp.models.trace import AgentTrace, TraceSpan
    from acp.primitives.audit.logger import EventType, log_event
    from acp.primitives.identity.service import register_agent
    from acp.primitives.policy.dsl import parse_and_compile

    if replace_existing:
        await db.execute(delete(ApprovalDecision).where(ApprovalDecision.request_id.in_(DEMO_APPROVAL_IDS)))
        await db.execute(delete(ApprovalRequest).where(ApprovalRequest.request_id.in_(DEMO_APPROVAL_IDS)))
        await db.execute(delete(TraceSpan).where(TraceSpan.trace_id.in_(DEMO_TRACE_IDS)))
        await db.execute(delete(AgentTrace).where(AgentTrace.trace_id.in_(DEMO_TRACE_IDS)))
        await db.execute(delete(PolicyDecisionLog).where(PolicyDecisionLog.agent_id.in_([a["agent_id"] for a in DEMO_AGENTS])))
        await db.execute(delete(PolicyVersion).where(PolicyVersion.policy_id.in_(DEMO_POLICY_IDS)))
        await db.execute(delete(Policy).where(Policy.policy_id.in_(DEMO_POLICY_IDS)))
        await db.execute(delete(AgentCredential).where(AgentCredential.agent_id.in_([a["agent_id"] for a in DEMO_AGENTS])))
        await db.execute(delete(Agent).where(Agent.agent_id.in_([a["agent_id"] for a in DEMO_AGENTS])))
        await db.execute(delete(RSAKeyPair).where(RSAKeyPair.org_id == DEMO_ORG_ID))
        await db.execute(delete(BudgetUsage).where(BudgetUsage.budget_id == DEMO_BUDGET_ID))
        await db.execute(delete(BudgetLimit).where(BudgetLimit.budget_id == DEMO_BUDGET_ID))
        # Clear all audit events so the hash chain rebuilds from genesis (prevents TAMPERED on re-seed)
        await db.execute(text("DELETE FROM audit_events"))
        await db.commit()

    now = datetime.now(tz=timezone.utc)

    for agent_spec in DEMO_AGENTS:
        agent, cred, _token = await register_agent(
            db,
            org_id=DEMO_ORG_ID,
            team_id=agent_spec["team_id"],
            display_name=agent_spec["display_name"],
            framework=agent_spec["framework"],
            environment=agent_spec["environment"],
            created_by=DEMO_ACTOR,
            tags=agent_spec["tags"],
            agent_id=agent_spec["agent_id"],
        )
        agent.last_seen_at = now - timedelta(minutes=5)
        await log_event(
            db,
            event_type=EventType.AGENT_REGISTERED,
            actor_type="user",
            actor_id=DEMO_ACTOR,
            resource_type="agent",
            resource_id=agent.agent_id,
            action="register",
            outcome="success",
            payload={"org_id": DEMO_ORG_ID, "team_id": agent.team_id, "framework": agent.framework},
        )
        await log_event(
            db,
            event_type=EventType.CREDENTIAL_ISSUED,
            actor_type="system",
            actor_id=DEMO_ACTOR,
            resource_type="credential",
            resource_id=cred.jti,
            action="issue",
            outcome="success",
            payload={"org_id": DEMO_ORG_ID, "agent_id": agent.agent_id},
        )

    for spec in DEMO_POLICY_SPECS:
        compiled = parse_and_compile(spec["dsl_source"])
        db.add(
            Policy(
                policy_id=compiled["policy_id"],
                org_id=DEMO_ORG_ID,
                scope_level=spec["scope_level"],
                scope_id=spec["scope_id"],
                description=compiled.get("description", ""),
                dsl_source=spec["dsl_source"],
                compiled=compiled,
                current_version=1,
                is_active=True,
                created_by=DEMO_ACTOR,
            )
        )
        db.add(
            PolicyVersion(
                policy_id=compiled["policy_id"],
                version=1,
                dsl_source=spec["dsl_source"],
                compiled=compiled,
                created_by=DEMO_ACTOR,
            )
        )
        await log_event(
            db,
            event_type=EventType.POLICY_CREATED,
            actor_type="user",
            actor_id=DEMO_ACTOR,
            resource_type="policy",
            resource_id=compiled["policy_id"],
            action="create",
            outcome="success",
            payload={"org_id": DEMO_ORG_ID, "scope_level": spec["scope_level"], "scope_id": spec["scope_id"]},
        )

    db.add_all([
        AgentTrace(
            trace_id=DEMO_TRACE_IDS[0],
            agent_id=DEMO_AGENTS[0]["agent_id"],
            org_id=DEMO_ORG_ID,
            team_id=DEMO_AGENTS[0]["team_id"],
            started_at=now - timedelta(minutes=18),
            ended_at=now - timedelta(minutes=17, seconds=43),
            duration_ms=17000,
            terminal_state="success",
            total_input_tokens=1820,
            total_output_tokens=460,
            total_cost_usd=0.01236,
            framework=DEMO_AGENTS[0]["framework"],
            environment=DEMO_AGENTS[0]["environment"],
        ),
        AgentTrace(
            trace_id=DEMO_TRACE_IDS[1],
            agent_id=DEMO_AGENTS[2]["agent_id"],
            org_id=DEMO_ORG_ID,
            team_id=DEMO_AGENTS[2]["team_id"],
            started_at=now - timedelta(minutes=8),
            ended_at=now - timedelta(minutes=7, seconds=48),
            duration_ms=12000,
            terminal_state="failure",
            total_input_tokens=320,
            total_output_tokens=0,
            total_cost_usd=0.00096,
            framework=DEMO_AGENTS[2]["framework"],
            environment=DEMO_AGENTS[2]["environment"],
        ),
    ])

    db.add_all([
        TraceSpan(
            span_id="66666666-6666-6666-6666-666666666661",
            trace_id=DEMO_TRACE_IDS[0],
            span_type="policy_check",
            name="Evaluate production LLM call",
            started_at=now - timedelta(minutes=18),
            ended_at=now - timedelta(minutes=18) + timedelta(milliseconds=6),
            duration_ms=6,
            inputs={"model_id": "claude-sonnet-4-6", "environment": "production"},
            outputs={
                "decision": "allow",
                "attestation": {
                    "verified": True,
                    "claims": {
                        "runtime_class": "cloud_run",
                        "build_digest": "sha256:demo-build",
                    },
                },
            },
            policy_decision="allow",
            policy_id="allow-attested-sonnet-in-prod",
            status="ok",
        ),
        TraceSpan(
            span_id="66666666-6666-6666-6666-666666666662",
            trace_id=DEMO_TRACE_IDS[0],
            span_type="llm_call",
            name="POST /v1/messages",
            started_at=now - timedelta(minutes=18) + timedelta(milliseconds=12),
            ended_at=now - timedelta(minutes=17, seconds=43),
            duration_ms=16988,
            model_id="claude-sonnet-4-6",
            input_tokens=1820,
            output_tokens=460,
            cost_usd=0.01236,
            inputs={"task": "Analyze payment exception queue"},
            outputs={"status": 200, "summary": "Recommended 2 manual reviews"},
            policy_decision="allow",
            policy_id="allow-attested-sonnet-in-prod",
            status="ok",
        ),
        TraceSpan(
            span_id="66666666-6666-6666-6666-666666666663",
            trace_id=DEMO_TRACE_IDS[1],
            span_type="policy_check",
            name="Block development write to production DB",
            started_at=now - timedelta(minutes=8),
            ended_at=now - timedelta(minutes=8) + timedelta(milliseconds=4),
            duration_ms=4,
            inputs={"operation": "INSERT", "table": "payments", "environment": "production"},
            outputs={"decision": "deny"},
            policy_decision="deny",
            policy_id="deny-dev-prod-db-writes",
            status="error",
            error="policy_violation",
        ),
        TraceSpan(
            span_id="66666666-6666-6666-6666-666666666664",
            trace_id=DEMO_TRACE_IDS[1],
            span_type="llm_call",
            name="POST /v1/messages",
            started_at=now - timedelta(minutes=7, seconds=58),
            ended_at=now - timedelta(minutes=7, seconds=48),
            duration_ms=10000,
            model_id="claude-opus-4-6",
            input_tokens=320,
            output_tokens=0,
            cost_usd=0.00096,
            inputs={"task": "Attempt direct production remediation"},
            outputs={"status": 403},
            policy_decision="deny",
            policy_id="deny-dev-prod-db-writes",
            status="error",
            error="blocked_by_policy",
        ),
    ])

    db.add_all([
        ApprovalRequest(
            request_id=DEMO_APPROVAL_IDS[0],
            agent_id=DEMO_AGENTS[0]["agent_id"],
            trace_id=DEMO_TRACE_IDS[0],
            policy_id="require-approval-for-opus-payments",
            action_type="llm_call",
            action_detail={"model_id": "claude-opus-4-6", "path": "/v1/messages", "risk": "payment-impacting"},
            requesting_user="alex.platform",
            status="pending",
            timeout_minutes=30,
            escalate_to="@maya.ciso",
            timeout_action="deny",
            created_at=now - timedelta(minutes=3),
            expires_at=now + timedelta(minutes=27),
            notified_channels=["slack#security-alerts"],
        ),
        ApprovalRequest(
            request_id=DEMO_APPROVAL_IDS[1],
            agent_id=DEMO_AGENTS[1]["agent_id"],
            trace_id=DEMO_TRACE_IDS[0],
            policy_id="require-approval-for-opus-payments",
            action_type="llm_call",
            action_detail={"model_id": "claude-opus-4-6", "path": "/v1/messages", "risk": "customer escalation"},
            requesting_user="jordan.ml",
            status="approved",
            timeout_minutes=30,
            escalate_to="@maya.ciso",
            timeout_action="deny",
            created_at=now - timedelta(minutes=40),
            expires_at=now - timedelta(minutes=10),
            decided_at=now - timedelta(minutes=34),
            decided_by="maya.ciso",
            decision_reason="Approved for customer-impacting incident response",
            approval_conditions={"max_duration_minutes": 10},
            notified_channels=["slack#security-alerts"],
        ),
        ApprovalDecision(
            request_id=DEMO_APPROVAL_IDS[1],
            action="approve",
            actor="maya.ciso",
            reason="Approved for customer-impacting incident response",
            conditions={"max_duration_minutes": 10},
        ),
    ])

    db.add_all([
        PolicyDecisionLog(
            agent_id=DEMO_AGENTS[0]["agent_id"],
            trace_id=DEMO_TRACE_IDS[0],
            action_type="llm_call",
            action_detail={"model_id": "claude-sonnet-4-6", "path": "/v1/messages"},
            matched_policy_id="allow-attested-sonnet-in-prod",
            decision="allow",
            decision_reason="Matched policy: allow-attested-sonnet-in-prod",
            evaluation_ms=6.2,
        ),
        PolicyDecisionLog(
            agent_id=DEMO_AGENTS[2]["agent_id"],
            trace_id=DEMO_TRACE_IDS[1],
            action_type="database_operation",
            action_detail={"operation": "INSERT", "table": "payments"},
            matched_policy_id="deny-dev-prod-db-writes",
            decision="deny",
            decision_reason="Matched policy: deny-dev-prod-db-writes",
            evaluation_ms=4.1,
        ),
    ])

    await log_event(
        db,
        event_type=EventType.APPROVAL_REQUESTED,
        actor_type="agent",
        actor_id=DEMO_AGENTS[0]["agent_id"],
        resource_type="approval_request",
        resource_id=DEMO_APPROVAL_IDS[0],
        action="request_approval",
        outcome="pending",
        payload={"org_id": DEMO_ORG_ID, "policy_id": "require-approval-for-opus-payments", "trace_id": DEMO_TRACE_IDS[0]},
    )
    await log_event(
        db,
        event_type=EventType.APPROVAL_APPROVED,
        actor_type="user",
        actor_id="maya.ciso",
        resource_type="approval_request",
        resource_id=DEMO_APPROVAL_IDS[1],
        action="approve",
        outcome="approved",
        payload={"org_id": DEMO_ORG_ID, "policy_id": "require-approval-for-opus-payments", "trace_id": DEMO_TRACE_IDS[0]},
    )
    await log_event(
        db,
        event_type=EventType.POLICY_VIOLATION,
        actor_type="agent",
        actor_id=DEMO_AGENTS[2]["agent_id"],
        resource_type="policy",
        resource_id="deny-dev-prod-db-writes",
        action="database_operation",
        outcome="blocked",
        payload={"org_id": DEMO_ORG_ID, "trace_id": DEMO_TRACE_IDS[1], "table": "payments"},
    )

    # ── Shadow agent detection trace ──────────────────────────────────────────
    db.add(AgentTrace(
        trace_id=DEMO_TRACE_IDS[2],
        agent_id=DEMO_AGENTS[3]["agent_id"],
        org_id=DEMO_ORG_ID,
        team_id=DEMO_AGENTS[3]["team_id"],
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=2) + timedelta(minutes=1, seconds=12),
        duration_ms=72000,
        terminal_state="failure",
        total_input_tokens=540,
        total_output_tokens=0,
        total_cost_usd=0.00162,
        framework=DEMO_AGENTS[3]["framework"],
        environment=DEMO_AGENTS[3]["environment"],
    ))
    db.add(TraceSpan(
        span_id="77777777-7777-7777-7777-777777777771",
        trace_id=DEMO_TRACE_IDS[2],
        span_type="policy_check",
        name="Shadow agent identity verification failed",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=2) + timedelta(milliseconds=3),
        duration_ms=3,
        inputs={"agent_id": DEMO_AGENTS[3]["agent_id"], "team_id": "team-unknown"},
        outputs={"decision": "deny", "reason": "agent registered outside approved onboarding — shadow agent detected"},
        policy_decision="deny",
        policy_id="deny-dev-prod-db-writes",
        status="error",
        error="shadow_agent_detected",
    ))
    await log_event(
        db,
        event_type=EventType.AGENT_REGISTERED,
        actor_type="agent",
        actor_id=DEMO_AGENTS[3]["agent_id"],
        resource_type="agent",
        resource_id=DEMO_AGENTS[3]["agent_id"],
        action="shadow_detected",
        outcome="blocked",
        payload={"org_id": DEMO_ORG_ID, "team_id": "team-unknown", "flag": "unregistered_source"},
    )

    # ── Agent delegation chain trace ──────────────────────────────────────────
    db.add(AgentTrace(
        trace_id=DEMO_TRACE_IDS[3],
        agent_id=DEMO_AGENTS[0]["agent_id"],
        org_id=DEMO_ORG_ID,
        team_id=DEMO_AGENTS[0]["team_id"],
        started_at=now - timedelta(hours=1),
        ended_at=now - timedelta(hours=1) + timedelta(minutes=2, seconds=8),
        duration_ms=128000,
        terminal_state="success",
        total_input_tokens=3200,
        total_output_tokens=940,
        total_cost_usd=0.04128,
        framework=DEMO_AGENTS[0]["framework"],
        environment=DEMO_AGENTS[0]["environment"],
    ))
    db.add_all([
        TraceSpan(
            span_id="88888888-8888-8888-8888-888888888881",
            trace_id=DEMO_TRACE_IDS[3],
            span_type="policy_check",
            name="Evaluate orchestrator delegation to support agent",
            started_at=now - timedelta(hours=1),
            ended_at=now - timedelta(hours=1) + timedelta(milliseconds=7),
            duration_ms=7,
            inputs={"delegating_agent": DEMO_AGENTS[0]["agent_id"], "target_agent": DEMO_AGENTS[1]["agent_id"]},
            outputs={"decision": "allow", "delegation_scope": "read_only"},
            policy_decision="allow",
            policy_id="allow-attested-sonnet-in-prod",
            status="ok",
        ),
        TraceSpan(
            span_id="88888888-8888-8888-8888-888888888882",
            trace_id=DEMO_TRACE_IDS[3],
            span_type="llm_call",
            name="Delegated: Support Triage summarize customer cases",
            started_at=now - timedelta(hours=1) + timedelta(milliseconds=20),
            ended_at=now - timedelta(hours=1) + timedelta(minutes=2, seconds=8),
            duration_ms=127980,
            model_id="claude-sonnet-4-6",
            input_tokens=3200,
            output_tokens=940,
            cost_usd=0.04128,
            inputs={"task": "Summarize 47 open support cases for finance review", "delegated_by": DEMO_AGENTS[0]["agent_id"]},
            outputs={"status": 200, "summary": "High-priority: 8 billing disputes, 3 SLA breaches"},
            policy_decision="allow",
            policy_id="allow-attested-sonnet-in-prod",
            status="ok",
        ),
    ])

    # ── Budget limit for demo org ─────────────────────────────────────────────
    budget = BudgetLimit(
        budget_id=DEMO_BUDGET_ID,
        org_id=DEMO_ORG_ID,
        scope_level="org",
        scope_id=DEMO_ORG_ID,
        max_tokens=None,
        max_cost_usd=500.00,
        window="rolling_30d",
        alert_thresholds=[50, 80, 95, 100],
        alert_channels=["slack#finance-alerts"],
        is_active=True,
        created_by=DEMO_ACTOR,
    )
    db.add(budget)
    await db.flush()
    # Seed usage at ~12% utilization so the bar is visible
    total_cost = sum([0.01236, 0.00096, 0.00162, 0.04128])
    db.add(BudgetUsage(
        budget_id=DEMO_BUDGET_ID,
        window_start=now - timedelta(days=14),
        window_end=now + timedelta(days=16),
        used_tokens=5880,
        used_cost_usd=total_cost,
        hard_stopped=False,
        model_breakdown={"claude-sonnet-4-6": round(0.01236 + 0.04128, 5), "claude-opus-4-6": round(0.00096 + 0.00162, 5)},
        last_updated=now,
    ))

    await db.commit()
    return {
        "agents": len(DEMO_AGENTS),
        "policies": len(DEMO_POLICY_SPECS),
        "traces": len(DEMO_TRACE_IDS),
        "approvals": len(DEMO_APPROVAL_IDS),
    }
