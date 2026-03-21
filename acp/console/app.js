const state = {
  currentView: "fleet",
  selectedTraceId: null,
  authenticated: false,
  pendingDecision: {},
  latest: { agents: [], policies: [], traces: [], approvals: [], budgets: [], auditEvents: [] },
};

const samplePolicy = `policy_id: "allow-attested-prod-sonnet"
description: "Allow production Sonnet calls only when runtime posture is verified"
subject:
  agent_environment: production
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
`;

document.addEventListener("DOMContentLoaded", () => {
  bindNav();
  bindRefresh();
  bindPolicyForm();
  bindBudgetForm();
  bindDemoScenario();
  bindAuth();
  bindAuditVerify();
  document.querySelector('textarea[name="dsl_source"]').value = samplePolicy;
  bootConsole();
});

async function bootConsole() {
  try {
    setStatus("Checking operator session...");
    const status = await fetchJson("/api/session/status");
    if (status.authenticated) {
      setAuthenticated(true);
      await refreshAll();
      return;
    }
    setAuthenticated(false);
    setStatus("Sign in required");
  } catch (error) {
    setAuthenticated(false);
    setStatus("Console locked", true);
    setAuthMessage(error.message, true);
  }
}

function bindAuth() {
  document.getElementById("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const token = document.getElementById("adminToken").value.trim();
    try {
      setAuthMessage("Authenticating operator...");
      const response = await fetch("/api/session/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Login failed");
      setAuthenticated(true);
      setAuthMessage("Access granted");
      setStatus("Operator authenticated");
      await refreshAll();
    } catch (error) {
      setAuthenticated(false);
      setStatus("Authentication failed", true);
      setAuthMessage(error.message, true);
    }
  });

  document.getElementById("logoutButton").addEventListener("click", async () => {
    try {
      await fetch("/api/session/logout", { method: "POST" });
    } finally {
      setAuthenticated(false);
      state.latest = { agents: [], policies: [], traces: [], approvals: [], budgets: [], auditEvents: [] };
      document.getElementById("overviewSnapshot").innerHTML = "";
      document.getElementById("fleetStats").innerHTML = "";
      document.getElementById("fleetTable").innerHTML = emptyMarkup("Sign in to view the fleet.");
      document.getElementById("fleetSpotlight").innerHTML = emptyMarkup("Sign in to unlock fleet posture.");
      document.getElementById("policyList").innerHTML = emptyMarkup("Sign in to view policies.");
      document.getElementById("traceList").innerHTML = emptyMarkup("Sign in to view traces.");
      document.getElementById("traceDetail").innerHTML = emptyMarkup("Sign in to inspect trace spans.");
      document.getElementById("approvalList").innerHTML = emptyMarkup("Sign in to review approvals.");
      document.getElementById("approvalSpotlight").innerHTML = emptyMarkup("Sign in to unlock approval posture.");
      setAuthMessage("Session closed. Sign in again to continue.");
      setStatus("Console locked");
    }
  });
}

function bindNav() {
  document.querySelectorAll(".nav-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach((btn) => btn.classList.remove("active"));
      button.classList.add("active");
      state.currentView = button.dataset.view;
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      document.getElementById(`${state.currentView}View`).classList.add("active");
    });
  });
}

function bindRefresh() {
  document.getElementById("refreshAll").addEventListener("click", refreshAll);
  document.getElementById("orgFilter").addEventListener("change", refreshAll);
}

function bindDemoScenario() {
  document.getElementById("runScenario").addEventListener("click", async () => {
    try {
      setStatus("Running demo scenario...");
      const response = await fetch("/api/demo/seed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ replace_existing: true }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to run demo scenario");
      document.getElementById("orgFilter").value = data.org_id;
      await refreshAll();
      setStatus("Demo scenario refreshed");
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

function bindPolicyForm() {
  document.getElementById("policyForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.target).entries());
    try {
      setStatus("Publishing policy...");
      const response = await fetch("/api/policies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Policy create failed");
      setStatus(`Policy ${data.policy_id} published`);
      event.target.reset();
      document.querySelector('textarea[name="dsl_source"]').value = samplePolicy;
      await loadPolicies();
      renderOverview();
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

async function refreshAll() {
  if (!state.authenticated) return;
  setStatus("Refreshing control plane...");
  try {
    await Promise.all([loadFleet(), loadPolicies(), loadTraces(), loadApprovals(), loadBudgets(), loadAudit()]);
    renderOverview();
    setStatus("Control plane refreshed");
  } catch (error) {
    setStatus(error.message, true);
  }
}

function getOrgFilter() {
  return document.getElementById("orgFilter").value.trim();
}

function toQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, value);
  });
  return query.toString() ? `?${query.toString()}` : "";
}

async function fetchJson(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (response.status === 401) {
    setAuthenticated(false);
    throw new Error(data.detail || "Operator authentication required");
  }
  if (!response.ok) throw new Error(data.detail || `Request failed: ${response.status}`);
  return data;
}

function setAuthenticated(isAuthenticated) {
  state.authenticated = isAuthenticated;
  document.getElementById("authShell").classList.toggle("hidden", isAuthenticated);
  document.querySelector(".shell").classList.toggle("locked", !isAuthenticated);
  document.getElementById("sessionState").textContent = isAuthenticated ? "Authenticated" : "Locked";
  document.getElementById("statusPill").classList.toggle("success", isAuthenticated);
  if (isAuthenticated) {
    setAuthMessage("");
    document.getElementById("adminToken").value = "";
  }
}

function setAuthMessage(message, isError = false) {
  const node = document.getElementById("authMessage");
  node.textContent = message;
  node.classList.toggle("danger", isError);
}

async function loadFleet() {
  try {
    const agents = await fetchJson(`/api/agents${toQuery({ org_id: getOrgFilter() })}`);
    state.latest.agents = agents;
    renderFleetStats(agents);
    renderFleetTable(agents);
    renderFleetSpotlight(agents);
  } catch (error) {
    renderError("fleetTable", error);
    renderError("fleetSpotlight", error);
  }
}

function renderFleetStats(agents) {
  const active = agents.filter((item) => item.status === "active").length;
  const prod = agents.filter((item) => item.environment === "production").length;
  const frameworks = new Set(agents.map((item) => item.framework)).size;
  const teams = new Set(agents.map((item) => item.team_id)).size;
  const seen = agents.filter((item) => item.last_seen_at).length;
  document.getElementById("fleetStats").innerHTML = [
    statCard("Registered", agents.length),
    statCard("Active", active),
    statCard("Production", prod),
    statCard("Frameworks", frameworks || 0),
    statCard("Seen Recently", seen),
  ].join("");
}

function renderFleetTable(agents) {
  if (!agents.length) {
    document.getElementById("fleetTable").innerHTML = emptyMarkup("No agents yet. Register one to populate the fleet.");
    return;
  }
  const rows = agents.map((agent) => `
    <tr>
      <td><strong>${escapeHtml(agent.display_name)}</strong><div class="muted">${escapeHtml(agent.agent_id)}</div></td>
      <td>${escapeHtml(agent.team_id)}</td>
      <td>${escapeHtml(agent.framework)}</td>
      <td>${statusPill(agent.environment, environmentClass(agent.environment))}</td>
      <td>${statusPill(agent.status)}</td>
      <td>${escapeHtml(formatTimestamp(agent.last_seen_at || "never"))}</td>
    </tr>`).join("");
  document.getElementById("fleetTable").innerHTML = `
    <div class="panel-topline">Live inventory</div>
    <h3>Registered Agents</h3>
    <table>
      <thead><tr><th>Agent</th><th>Team</th><th>Framework</th><th>Environment</th><th>Status</th><th>Last Seen</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderFleetSpotlight(agents) {
  if (!agents.length) {
    document.getElementById("fleetSpotlight").innerHTML = emptyMarkup("Fleet insights will appear here once agents are registered.");
    return;
  }
  const productionNames = agents.filter((agent) => agent.environment === "production").map((agent) => agent.display_name);
  const mostRecent = [...agents].sort((a, b) => String(b.last_seen_at || "").localeCompare(String(a.last_seen_at || "")))[0];
  const attestedPolicies = state.latest.policies.filter((policy) => policy.compiled?.conditions?.attestation).length;
  document.getElementById("fleetSpotlight").innerHTML = `
    <div class="panel-topline">Operator Spotlight</div>
    <h3>Fleet Posture</h3>
    <div class="spotlight-stack">
      <div class="spotlight-stat"><div class="spotlight-label">Production Coverage</div><div class="spotlight-value">${escapeHtml(String(productionNames.length))}</div><p>${escapeHtml(productionNames.slice(0, 2).join(", ") || "No production agents yet")}</p></div>
      <div class="spotlight-stat"><div class="spotlight-label">Most Recently Seen</div><div class="spotlight-value">${escapeHtml(mostRecent.display_name)}</div><p>${escapeHtml(formatTimestamp(mostRecent.last_seen_at || "never"))}</p></div>
      <div class="spotlight-stat"><div class="spotlight-label">Attestation-Aware Policies</div><div class="spotlight-value">${escapeHtml(String(attestedPolicies))}</div><p>Policies can require verified runtime posture before production actions are allowed.</p></div>
    </div>`;
}

async function loadPolicies() {
  try {
    const policies = await fetchJson(`/api/policies${toQuery({ org_id: getOrgFilter() })}`);
    state.latest.policies = policies;
    const container = document.getElementById("policyList");
    if (!policies.length) {
      container.innerHTML = emptyMarkup("No policies yet. Create your first rule from the form.");
      return;
    }
    container.innerHTML = policies.map((policy) => `
      <article class="list-card">
        ${statusPill(`${policy.scope_level} scope`, "neutral")}
        ${policy.compiled?.conditions?.attestation ? statusPill("attestation required") : ""}
        <h4>${escapeHtml(policy.policy_id)}</h4>
        <p>${escapeHtml(policy.description || "No description")}</p>
        <p class="muted">Version ${escapeHtml(String(policy.current_version))} · scope_id ${escapeHtml(policy.scope_id)}</p>
        <pre>${escapeHtml(policy.dsl_source)}</pre>
      </article>`).join("");
  } catch (error) {
    renderError("policyList", error);
  }
}

async function loadTraces() {
  try {
    const traces = await fetchJson(`/api/traces${toQuery({ org_id: getOrgFilter(), limit: 20 })}`);
    state.latest.traces = traces;
    const container = document.getElementById("traceList");
    if (!traces.length) {
      container.innerHTML = emptyMarkup("No traces captured yet. Run an agent through the proxy to see activity.");
      document.getElementById("traceDetail").innerHTML = emptyMarkup("Select a trace to inspect spans.");
      return;
    }
    if (!state.selectedTraceId || !traces.some((trace) => trace.trace_id === state.selectedTraceId)) state.selectedTraceId = traces[0].trace_id;
    container.innerHTML = traces.map((trace) => `
      <button class="list-card trace-card ${trace.trace_id === state.selectedTraceId ? "selected" : ""}" data-trace-id="${escapeHtml(trace.trace_id)}">
        ${statusPill(trace.terminal_state || "running", trace.terminal_state === "failure" ? "danger" : "")}
        <h4>${escapeHtml(trace.trace_id)}</h4>
        <p>${escapeHtml(trace.agent_id)} · ${escapeHtml(trace.framework || "unknown framework")}</p>
        <p class="muted">$${escapeHtml((trace.total_cost_usd || 0).toFixed(6))} · ${escapeHtml(String(trace.total_input_tokens || 0))} in / ${escapeHtml(String(trace.total_output_tokens || 0))} out</p>
      </button>`).join("");
    document.querySelectorAll(".trace-card").forEach((button) => {
      button.addEventListener("click", async () => {
        state.selectedTraceId = button.dataset.traceId;
        await loadTraceDetail(state.selectedTraceId);
        renderTraceSelection();
      });
    });
    await loadTraceDetail(state.selectedTraceId);
  } catch (error) {
    renderError("traceList", error);
    renderError("traceDetail", error);
  }
}

function renderTraceSelection() {
  document.querySelectorAll(".trace-card").forEach((button) => {
    button.classList.toggle("selected", button.dataset.traceId === state.selectedTraceId);
  });
}

async function loadTraceDetail(traceId) {
  try {
    const trace = await fetchJson(`/api/traces/${traceId}`);
    const attestation = extractTraceAttestation(trace);
    const spans = (trace.spans || []).map((span) => `
      <article class="list-card">
        ${statusPill(span.span_type, span.status === "error" ? "danger" : "neutral")}
        <h4>${escapeHtml(span.name)}</h4>
        <p class="muted">Model: ${escapeHtml(span.model_id || "n/a")} · Cost: $${escapeHtml(String(span.cost_usd || 0))} · Policy: ${escapeHtml(span.policy_decision || "n/a")}</p>
        <pre>${escapeHtml(JSON.stringify({ inputs: span.inputs, outputs: span.outputs, error: span.error }, null, 2))}</pre>
      </article>`).join("");
    document.getElementById("traceDetail").innerHTML = `
      <div class="list-card">
        ${statusPill(trace.terminal_state || "running", trace.terminal_state === "failure" ? "danger" : "")}
        ${attestation ? statusPill(attestation.verified ? "attested runtime" : "unverified runtime", attestation.verified ? "" : "warn") : ""}
        <h4>${escapeHtml(trace.trace_id)}</h4>
        <p>${escapeHtml(trace.agent_id)} · ${escapeHtml(trace.environment || "unknown environment")} · ${escapeHtml(trace.framework || "unknown framework")}</p>
        <p class="muted">Total cost $${escapeHtml(Number(trace.total_cost_usd || 0).toFixed(6))} · ${escapeHtml(String(trace.spans.length))} spans</p>
      </div>
      ${renderAttestationSummary(attestation)}
      <div class="list">${spans || emptyMarkup("This trace has no spans yet.")}</div>`;
    renderTraceSelection();
  } catch (error) {
    renderError("traceDetail", error);
  }
}

async function loadApprovals() {
  try {
    const approvals = await fetchJson(`/api/approvals${toQuery({ org_id: getOrgFilter(), limit: 20 })}`);
    state.latest.approvals = approvals;
    const container = document.getElementById("approvalList");
    if (!approvals.length) {
      container.innerHTML = emptyMarkup("No approval requests yet. Approval-required policies will show up here.");
      document.getElementById("approvalSpotlight").innerHTML = emptyMarkup("Approval posture appears here when requests arrive.");
      return;
    }
    container.innerHTML = approvals.map((item) => {
      const isPending = item.status === "pending";
      const decisionMeta = item.decided_by
        ? `<p class="muted" style="margin-top:8px;">Decided by <strong>${escapeHtml(item.decided_by)}</strong>${item.decision_reason ? " — " + escapeHtml(item.decision_reason) : ""}</p>`
        : "";
      const actions = isPending ? `
        <div class="approval-actions" style="margin-top:12px;">
          <div class="action-row" style="gap:8px;">
            <button class="primary-btn approve-btn" data-id="${escapeHtml(item.request_id)}" style="padding:8px 14px;font-size:0.85rem;background:#16a34a;">Approve</button>
            <button class="secondary-btn deny-btn" data-id="${escapeHtml(item.request_id)}" style="padding:8px 14px;font-size:0.85rem;">Deny</button>
            <button class="secondary-btn escalate-btn" data-id="${escapeHtml(item.request_id)}" style="padding:8px 14px;font-size:0.85rem;">Escalate</button>
          </div>
          <div class="decision-form" id="decision-form-${escapeHtml(item.request_id)}" style="display:none;margin-top:12px;">
            <label class="field compact">
              <span>Reason (optional)</span>
              <input type="text" class="decision-reason" placeholder="Brief justification for audit record..." />
            </label>
            <div class="action-row" style="gap:8px;margin-top:6px;">
              <button class="primary-btn confirm-decision-btn" data-id="${escapeHtml(item.request_id)}" style="padding:8px 14px;font-size:0.85rem;">Confirm</button>
              <button class="secondary-btn cancel-decision-btn" data-id="${escapeHtml(item.request_id)}" style="padding:8px 14px;font-size:0.85rem;">Cancel</button>
            </div>
          </div>
        </div>` : "";
      const channels = item.notified_channels || [];
      const notifyBadge = channels.length
        ? `<p class="muted" style="margin-top:6px;">📣 Notified: ${channels.map((c) => `<code>${escapeHtml(c)}</code>`).join(", ")}</p>`
        : `<p class="muted" style="margin-top:6px;opacity:0.6;">No notification channels configured</p>`;
      return `
        <article class="list-card">
          ${statusPill(item.status, approvalClass(item.status))}
          <h4>${escapeHtml(item.request_id)}</h4>
          <p>${escapeHtml(item.agent_id)} · ${escapeHtml(item.action_type)}</p>
          <p class="muted">Policy ${escapeHtml(item.policy_id || "unknown")} · expires ${escapeHtml(formatTimestamp(item.expires_at))}</p>
          <pre>${escapeHtml(JSON.stringify(item.action_detail, null, 2))}</pre>
          ${notifyBadge}
          ${decisionMeta}
          ${actions}
        </article>`;
    }).join("");
    bindApprovalDecisions();
    renderApprovalSpotlight(approvals);
  } catch (error) {
    renderError("approvalList", error);
    renderError("approvalSpotlight", error);
  }
}

function bindApprovalDecisions() {
  const container = document.getElementById("approvalList");

  container.querySelectorAll(".approve-btn, .deny-btn, .escalate-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const action = btn.classList.contains("approve-btn") ? "approve" : btn.classList.contains("deny-btn") ? "deny" : "escalate";
      state.pendingDecision[id] = action;
      const form = document.getElementById(`decision-form-${id}`);
      if (!form) return;
      const confirmBtn = form.querySelector(".confirm-decision-btn");
      const colors = { approve: "#16a34a", deny: "#d92d20", escalate: "#b7791f" };
      confirmBtn.textContent = `Confirm ${action.charAt(0).toUpperCase() + action.slice(1)}`;
      confirmBtn.style.background = colors[action];
      form.style.display = "block";
    });
  });

  container.querySelectorAll(".confirm-decision-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      const action = state.pendingDecision[id];
      if (!action) return;
      const form = document.getElementById(`decision-form-${id}`);
      const reason = form ? form.querySelector(".decision-reason").value.trim() : "";
      try {
        setStatus(`Submitting ${action}...`);
        const response = await fetch(`/api/approvals/${id}/decide`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, actor: "console-operator", reason: reason || null }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Decision failed");
        delete state.pendingDecision[id];
        setStatus(`Decision recorded: ${action}`);
        await loadApprovals();
        await loadAudit();
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  });

  container.querySelectorAll(".cancel-decision-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const form = document.getElementById(`decision-form-${btn.dataset.id}`);
      if (form) form.style.display = "none";
      delete state.pendingDecision[btn.dataset.id];
    });
  });
}

function renderApprovalSpotlight(approvals) {
  const pending = approvals.filter((item) => item.status === "pending").length;
  const approved = approvals.filter((item) => item.status === "approved").length;
  const escalated = approvals.filter((item) => item.status === "escalated").length;
  document.getElementById("approvalSpotlight").innerHTML = `
    <div class="panel-topline">Oversight Posture</div>
    <h3>Decision Velocity</h3>
    <div class="spotlight-stack">
      <div class="spotlight-stat"><div class="spotlight-label">Pending Decisions</div><div class="spotlight-value">${escapeHtml(String(pending))}</div><p>Requests currently waiting on a human response.</p></div>
      <div class="spotlight-stat"><div class="spotlight-label">Approved</div><div class="spotlight-value">${escapeHtml(String(approved))}</div><p>Actions already unblocked with explicit oversight.</p></div>
      <div class="spotlight-stat"><div class="spotlight-label">Escalated</div><div class="spotlight-value">${escapeHtml(String(escalated))}</div><p>Cases routed beyond the initial approver tier.</p></div>
    </div>`;
}

function renderOverview() {
  const { agents, policies, traces, approvals } = state.latest;
  const riskyTraces = traces.filter((trace) => trace.terminal_state === "failure").length;
  const pendingApprovals = approvals.filter((item) => item.status === "pending").length;
  const productionAgents = agents.filter((item) => item.environment === "production").length;
  const observedRunCost = traces.reduce((sum, trace) => sum + Number(trace.total_cost_usd || 0), 0);
  const attestationAwarePolicies = policies.filter((policy) => policy.compiled?.conditions?.attestation).length;
  document.getElementById("overviewSnapshot").innerHTML = [
    snapshotCard("Production Agents", productionAgents, "Protected identities in prod", [42, 58, 54, 60, 74, 78, 80, 76, 82, 92]),
    snapshotCard("Attested Policies", attestationAwarePolicies, "Rules that require verified runtime posture", [18, 24, 28, 30, 44, 40, 55, 52, 60, 68]),
    snapshotCard("Pending Approvals", pendingApprovals, "Human reviews awaiting a decision", [66, 60, 55, 58, 44, 40, 36, 42, 38, 34]),
      snapshotCard("Observed Run Cost", `$${observedRunCost.toFixed(4)}`, `${riskyTraces} traces need attention`, [14, 22, 26, 24, 38, 44, 52, 58, 64, 72]),
  ].join("");
  renderHeroAttestation(attestationAwarePolicies, traces);
  animateSnapshotValues();
}

function renderHeroAttestation(attestationAwarePolicies, traces) {
  const attestedTrace = traces.find((trace) => trace.terminal_state === "success");
  const node = document.getElementById("heroAttestation");
  if (!node) return;
  node.innerHTML = `
    <div class="hero-signal-label">Attestation</div>
    <div class="hero-signal-value">${escapeHtml(String(attestationAwarePolicies))} attestation-aware policies</div>
    <p class="hero-signal-copy">${escapeHtml(attestedTrace ? "Verified runtime posture can now gate production actions before execution begins." : "AIS-style runtime claims can be verified and enforced directly in policy.")}</p>
  `;
}

function extractTraceAttestation(trace) {
  const policySpan = (trace.spans || []).find((span) => span.span_type === "policy_check" && span.outputs?.attestation);
  return policySpan?.outputs?.attestation || null;
}

function renderAttestationSummary(attestation) {
  if (!attestation) return "";
  const claims = attestation.claims || {};
  const claimLines = Object.entries(claims).map(([key, value]) => `<li><strong>${escapeHtml(key)}</strong> ${escapeHtml(String(value))}</li>`).join("");
  return `
    <article class="list-card">
      <div class="panel-topline">Runtime Posture</div>
      <h4>Attestation Summary</h4>
      <p class="muted">This run includes runtime claims that can be enforced in policy before production actions are allowed.</p>
      <div class="pill-row">
        ${statusPill(attestation.verified ? "verified" : "unverified", attestation.verified ? "" : "warn")}
      </div>
      <ul class="claim-list">${claimLines || "<li>No attestation claims provided.</li>"}</ul>
    </article>`;
}

function statCard(label, value) {
  return `<div class="stat"><div class="stat-label">${escapeHtml(label)}</div><div class="stat-value">${escapeHtml(String(value))}</div></div>`;
}

function snapshotCard(label, value, footnote, sparkValues) {
  const bars = sparkValues.map((height, index) =>
    `<span class="spark-bar" style="height:${height}%; animation-delay:${index * 30}ms"></span>`
  ).join("");
  const numericValue = typeof value === "number" ? value : (String(value).startsWith("$") ? Number(String(value).slice(1)) : null);
  return `<article class="snapshot-card">
    <div class="snapshot-label">${escapeHtml(label)}</div>
    <div class="snapshot-value" ${numericValue !== null && !Number.isNaN(numericValue) ? `data-animate-value="${numericValue}" data-prefix="${String(value).startsWith("$") ? "$" : ""}" data-decimals="${String(value).includes(".") ? 4 : 0}"` : ""}>${escapeHtml(String(value))}</div>
    <div class="snapshot-footnote">${escapeHtml(footnote)}</div>
    <div class="sparkline" aria-hidden="true">${bars}</div>
  </article>`;
}

function animateSnapshotValues() {
  document.querySelectorAll("[data-animate-value]").forEach((node) => {
    const target = Number(node.dataset.animateValue);
    const prefix = node.dataset.prefix || "";
    const decimals = Number(node.dataset.decimals || 0);
    const duration = 650;
    const start = performance.now();
    function tick(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = target * eased;
      node.textContent = `${prefix}${value.toFixed(decimals)}`;
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });
}

async function loadBudgets() {
  try {
    const budgets = await fetchJson(`/api/budgets${toQuery({ org_id: getOrgFilter() })}`);
    if (!budgets.length) {
      state.latest.budgets = [];
      document.getElementById("budgetList").innerHTML = emptyMarkup("No budget limits set. Use the form to cap agent spend by org, team, or agent.");
      return;
    }
    const withUsage = await Promise.all(
      budgets.map(async (b) => {
        try {
          const usage = await fetchJson(`/api/budgets/${b.budget_id}/usage`);
          return { ...b, usage };
        } catch {
          return { ...b, usage: null };
        }
      })
    );
    state.latest.budgets = withUsage;
    renderBudgetList(withUsage);
  } catch (error) {
    renderError("budgetList", error);
  }
}

function renderBudgetList(budgets) {
  document.getElementById("budgetList").innerHTML = budgets.map((b) => {
    const usage = b.usage;
    const pct = usage ? Math.min(Math.round(usage.pct_cost_used), 100) : 0;
    const barClass = pct >= 95 ? "danger" : pct >= 80 ? "warn" : "";
    const used = usage ? `$${Number(usage.used_cost_usd).toFixed(4)}` : "—";
    const max = b.max_cost_usd != null ? `$${Number(b.max_cost_usd).toFixed(2)}` : "—";
    const hardStop = usage && usage.hard_stopped ? statusPill("hard stopped", "danger") : "";
    return `
      <article class="list-card">
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">
          ${statusPill(b.scope_level, "neutral")} ${statusPill(b.window, "neutral")} ${hardStop}
        </div>
        <h4>${escapeHtml(b.scope_id)}</h4>
        <p class="muted">Limit ${escapeHtml(max)} · Used ${escapeHtml(used)} · ${escapeHtml(String(pct))}%</p>
        <div class="utilization-track">
          <div class="utilization-bar ${barClass}" style="width:${escapeHtml(String(pct))}%"></div>
        </div>
      </article>`;
  }).join("");
}

function bindBudgetForm() {
  document.getElementById("budgetForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const raw = Object.fromEntries(new FormData(event.target).entries());
    const payload = { ...raw };
    if (payload.max_cost_usd) payload.max_cost_usd = Number(payload.max_cost_usd);
    else delete payload.max_cost_usd;
    try {
      setStatus("Creating budget limit...");
      const response = await fetch("/api/budgets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Budget create failed");
      setStatus(`Budget limit set for ${data.scope_id}`);
      event.target.reset();
      await loadBudgets();
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

async function loadAudit() {
  try {
    const params = { limit: 50 };
    if (getOrgFilter()) params.org_id = getOrgFilter();
    const events = await fetchJson(`/api/audit/events${toQuery(params)}`);
    state.latest.auditEvents = events;
    renderAuditList(events);
  } catch (error) {
    renderError("auditList", error);
  }
}

function renderAuditList(events) {
  const container = document.getElementById("auditList");
  if (!events || !events.length) {
    container.innerHTML = emptyMarkup("No audit events yet. Activity will appear as agents are registered and policies are evaluated.");
    return;
  }
  const outcomeClass = (o) => {
    if (o === "success" || o === "approved" || o === "allow") return "";
    if (o === "blocked" || o === "denied" || o === "failure") return "danger";
    return "neutral";
  };
  container.innerHTML = events.map((e) => `
    <article class="list-card audit-event">
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px;">
        ${statusPill(e.event_type, "neutral")} ${statusPill(e.outcome, outcomeClass(e.outcome))}
      </div>
      <p style="margin:0;"><strong>${escapeHtml(e.actor_id)}</strong> · ${escapeHtml(e.action)} on ${escapeHtml(e.resource_type)}</p>
      <p class="muted" style="margin:4px 0 0;font-size:0.82rem;font-family:monospace;">${escapeHtml(e.resource_id)}</p>
      <p class="muted" style="margin:4px 0 0;font-size:0.82rem;">${escapeHtml(formatTimestamp(e.timestamp))}</p>
    </article>`).join("");
}

function bindAuditVerify() {
  const btn = document.getElementById("verifyChain");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    btn.textContent = "Verifying…";
    btn.disabled = true;
    try {
      const result = await fetchJson("/api/audit/verify");
      const el = document.getElementById("chainStatus");
      el.innerHTML = `<div class="chain-result ${result.valid ? "chain-ok" : "chain-fail"}">${result.valid ? "Chain intact — all events verified. Tamper-proof record confirmed." : "Tampering detected at event " + escapeHtml(result.tampered_event_id || "unknown")}</div>`;
    } catch (error) {
      document.getElementById("chainStatus").innerHTML = `<div class="chain-result chain-fail">${escapeHtml(error.message)}</div>`;
    } finally {
      btn.textContent = "Verify Chain Integrity";
      btn.disabled = false;
    }
  });
}

function approvalClass(status) {
  if (status === "denied" || status === "timed_out") return "danger";
  if (status === "pending" || status === "escalated") return "warn";
  return "";
}

function environmentClass(environment) {
  if (environment === "production") return "";
  if (environment === "staging") return "warn";
  return "neutral";
}

function statusPill(status, klass = "") {
  return `<span class="pill ${klass}">${escapeHtml(status)}</span>`;
}

function renderError(elementId, error) {
  document.getElementById(elementId).innerHTML = `<div class="panel empty-state">Unable to load this section.<br />${escapeHtml(error.message)}</div>`;
  setStatus(error.message, true);
}

function emptyMarkup(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function setStatus(message, isError = false) {
  const pill = document.getElementById("statusPill");
  pill.textContent = message;
  pill.classList.toggle("danger", isError);
  pill.classList.toggle("success", !isError && state.authenticated);
}

function formatTimestamp(value) {
  if (!value || value === "never") return "never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
