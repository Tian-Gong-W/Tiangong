(() => {
  "use strict";

  const form = document.getElementById("mission-form");
  if (!form) return;

  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const target = document.getElementById("mission-input");
  const iterations = document.getElementById("max-iterations");
  const executions = document.getElementById("max-executions");
  const duration = document.getElementById("max-duration");
  const submit = form.querySelector('button[type="submit"]');
  const actions = form.querySelector(".dialog-actions");
  const note = form.querySelector(".dialog-note");

  // Console used to hard-code 300s even after MissionLoop's governed default moved
  // to 1200s. Upgrade only the legacy untouched value; never overwrite an
  // operator-selected duration.
  if (duration && duration.value === "300") duration.value = "1200";
  const budgetDuration = document.querySelector(".budget span:nth-child(3) b");
  if (budgetDuration && budgetDuration.textContent.trim() === "300s") budgetDuration.textContent = "1200s";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost mission-preflight-button";
  button.textContent = "◎ 任務預檢";
  actions?.insertBefore(button, submit || null);

  const result = document.createElement("div");
  result.id = "mission-preflight-result";
  result.className = "mission-preflight-result hidden";
  note?.insertAdjacentElement("afterend", result);

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));

  function requestBody() {
    return {
      target: target?.value?.trim() || "",
      max_iterations: Number(iterations?.value || 8),
      max_executions: Number(executions?.value || 3),
      max_duration_seconds: Number(duration?.value || 1200),
      assessment_rounds: 0,
      subagents_per_round: 0,
    };
  }

  async function api(body) {
    const response = await fetch("/api/missions/preflight", {
      method: "POST",
      cache: "no-store",
      headers: {"Content-Type":"application/json", "X-TONMEN-CSRF":csrf},
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data;
  }

  function issueRows(items, tone) {
    return (items || []).map(item => `<div class="preflight-issue ${tone}"><strong>${esc(item.code)}</strong><span>${esc(item.message)}</span>${item.remediation ? `<small>${esc(item.remediation)}</small>` : ""}</div>`).join("");
  }

  function render(data) {
    const policy = data.policy || {};
    const plane = data.execution_plane || {};
    const assets = data.assets || {};
    const council = data.ai?.council || {};
    const planMeta = data.plan?.metadata?.coverage_plan || {};
    const steps = (data.steps || []).map(step => {
      const readiness = step.readiness || {};
      const ready = readiness.ready === true ? "READY" : readiness.ready === false ? "BLOCKED" : "WORKER CHECK";
      const tone = readiness.ready === false ? "bad" : readiness.ready === true ? "ok" : "remote";
      return `<tr><td>${esc(step.tool)}</td><td><code>${esc(step.target)}</code></td><td>${esc(step.timeout_seconds)}s</td><td>${step.requires_approval ? "yes" : "no"}</td><td><span class="preflight-state ${tone}">${ready}</span></td></tr>`;
    }).join("");
    const resolved = (assets.resolved_addresses || []).map(address => {
      const authorized = (assets.authorized_addresses || []).includes(address);
      return `<span class="preflight-asset ${authorized ? "ok" : "warn"}">${esc(address)} · ${authorized ? "SCOPE" : "NEEDS SCOPE"}</span>`;
    }).join("");
    const recommended = Number(planMeta.recommended_max_executions || 0);
    const coverageHint = assets.coverage_enabled && recommended > Number(executions?.value || 0)
      ? `<div class="preflight-budget-hint">Resolved-IP coverage generates ${esc(data.plan?.steps || 0)} step(s). Recommended execution budget: <b>${esc(recommended)}</b>. <button type="button" data-apply-execution-budget="${esc(recommended)}">套用</button></div>`
      : "";

    result.className = `mission-preflight-result ${data.ready_to_start ? "ready" : "blocked"}`;
    result.innerHTML = `
      <div class="preflight-head"><div><strong>${data.ready_to_start ? "✓ 可啟動" : "× 有阻擋"}</strong><span>${esc(plane.mode || "local")} execution · ${esc(data.plan?.steps || 0)} steps · max ${esc(policy.max_duration_seconds || 0)}s</span></div><span>${esc(council.model_backed ? "COUNCIL MODEL" : "COUNCIL FALLBACK")}</span></div>
      ${coverageHint}
      ${issueRows(data.blockers, "bad")}${issueRows(data.warnings, "warn")}
      <div class="preflight-grid"><div><span>Longest step timeout</span><strong>${esc(policy.longest_step_timeout_seconds || 0)}s</strong></div><div><span>Approval gates</span><strong>${esc(data.plan?.approval_gated_steps || 0)}</strong></div><div><span>AI pool</span><strong>${esc((council.pool || []).join(", ") || "empty")}</strong></div><div><span>Worker health</span><strong>${plane.health_probe_deferred ? "dispatch-time" : "local"}</strong></div></div>
      <div class="preflight-assets">${resolved || `<span class="preflight-asset">No concrete A/AAAA observation</span>`}</div>
      <div class="preflight-table-wrap"><table><thead><tr><th>Tool</th><th>Target</th><th>Timeout</th><th>Approval</th><th>Readiness</th></tr></thead><tbody>${steps}</tbody></table></div>`;
    if (submit) submit.disabled = !data.ready_to_start;
    result.querySelector("[data-apply-execution-budget]")?.addEventListener("click", event => {
      const value = Number(event.currentTarget.dataset.applyExecutionBudget || 0);
      if (executions && value > 0) executions.value = String(value);
      event.currentTarget.closest(".preflight-budget-hint")?.remove();
    });
  }

  function invalidate() {
    result.className = "mission-preflight-result hidden";
    result.innerHTML = "";
    if (submit) submit.disabled = false;
  }

  [target, iterations, executions, duration].forEach(input => input?.addEventListener("input", invalidate));

  button.addEventListener("click", async () => {
    const body = requestBody();
    if (!body.target) {
      result.className = "mission-preflight-result blocked";
      result.innerHTML = '<div class="preflight-issue bad"><strong>target_required</strong><span>請先輸入已授權目標。</span></div>';
      return;
    }
    button.disabled = true;
    button.textContent = "預檢中…";
    result.className = "mission-preflight-result loading";
    result.innerHTML = "正在建立 governed plan、檢查 Scope / timeout / Provider / execution plane…";
    try {
      render(await api(body));
    } catch (error) {
      result.className = "mission-preflight-result blocked";
      result.innerHTML = `<div class="preflight-issue bad"><strong>preflight_failed</strong><span>${esc(error.message || error)}</span></div>`;
      if (submit) submit.disabled = true;
    } finally {
      button.disabled = false;
      button.textContent = "◎ 任務預檢";
    }
  });
})();
