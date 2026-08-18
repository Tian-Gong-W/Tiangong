(() => {
  "use strict";

  const TRACE_TAB = "decision-trace";
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
  const short = value => String(value || "").slice(0, 8);
  let busy = false;

  function selectedRun() {
    const explicit = new URLSearchParams(location.search).get("run");
    if (explicit) return explicit;
    return document.querySelector("#module-page-root .module-table tr.selected[data-select-run]")?.dataset.selectRun || null;
  }

  function nodeMap(detail) {
    return new Map((detail.graph?.nodes || []).map(node => [node.id, node]));
  }

  function edgesFrom(detail, source, relation) {
    return (detail.graph?.edges || []).filter(edge => edge.source === source && (!relation || edge.relation === relation));
  }

  function basisHtml(ids, nodes) {
    const values = (ids || []).map(id => nodes.get(id)).filter(Boolean);
    if (!values.length) return `<span class="trace-muted">依据：暂无 Fact</span>`;
    return `<div class="trace-basis"><span>Evidence basis</span>${values.map(node => `<span class="trace-fact" title="${esc(node.id)}">${esc(node.label)}</span>`).join("")}</div>`;
  }

  function latestProfile(detail) {
    const graphNodes = detail.graph?.nodes || [];
    const rounds = graphNodes.filter(node => node.kind === "council.round" && node.metadata?.target_profile);
    if (rounds.length) return rounds.at(-1).metadata.target_profile;
    const adaptiveSteps = (detail.steps || []).filter(step => step.metadata?.adaptive_profile);
    if (adaptiveSteps.length) return adaptiveSteps.at(-1).metadata.adaptive_profile;
    return null;
  }

  function profilePanel(detail) {
    const profile = latestProfile(detail);
    const revisions = (detail.graph?.nodes || []).filter(node => node.kind === "planning.revision").length;
    const rounds = (detail.graph?.nodes || []).filter(node => node.kind === "council.round").length;
    const decisions = (detail.reasoning || []).length;
    if (!profile) {
      return `<div class="trace-profile"><div><span>Target Profile</span><strong>等待 Evidence</strong><small>Seed 执行后会生成实时 Profile。</small></div><div><span>Plan revisions</span><strong>${revisions}</strong></div><div><span>Decisions</span><strong>${decisions}</strong></div><div><span>Council rounds</span><strong>${rounds}</strong></div></div>`;
    }
    const unknowns = profile.unknowns || [];
    const hypotheses = profile.hypotheses || [];
    return `<div class="trace-profile">
      <div><span>Target Profile</span><strong>${esc(profile.kind || "unknown")}</strong><small>complexity ${esc(profile.complexity ?? "—")}</small></div>
      <div><span>Unknowns</span><strong>${unknowns.length}</strong><small>${esc(unknowns.join(" · ") || "none")}</small></div>
      <div><span>Hypotheses</span><strong>${hypotheses.length}</strong><small>${esc(hypotheses.join(" · ") || "none")}</small></div>
      <div><span>Replan / Decision / Council</span><strong>${revisions} / ${decisions} / ${rounds}</strong><small>all evidence-backed</small></div>
    </div>`;
  }

  function seedItem(detail) {
    const first = (detail.steps || [])[0];
    if (!first) return "";
    return `<article class="trace-item seed"><div class="trace-rail"><span>SEED</span></div><div class="trace-card"><div class="trace-head"><strong>初始最小探测 · ${esc(first.tool)}</strong><span>无自我扩权</span></div><p>${esc(first.rationale || "Start from the smallest governed observation.")}</p><div class="trace-meta"><span>Target ${esc(first.target)}</span><span>State ${esc(first.state)}</span><span>Risk L${esc(first.risk ?? "—")}</span></div></div></article>`;
  }

  function revisionItem(node, nodes) {
    const md = node.metadata || {};
    return `<article class="trace-item plan"><div class="trace-rail"><span>PLAN+</span></div><div class="trace-card"><div class="trace-head"><strong>Evidence 驱动追加 · ${esc(md.tool || node.label)}</strong><span>${md.requires_approval ? "下一治理边界：审批" : "可进入受控执行"}</span></div><p>${esc(md.rationale || node.label)}</p><div class="trace-callout"><b>预期信息增益</b><span>${esc(md.expected_information_gain || "—")}</span></div>${basisHtml(md.basis_fact_ids, nodes)}<div class="trace-meta"><span>Risk L${esc(md.risk ?? "—")}</span><span>Unknowns ${esc((md.profile_unknowns || []).join(" · ") || "none")}</span><span>execution_authority=${md.execution_authority === false ? "false" : "—"}</span></div></div></article>`;
  }

  function reasoningItem(node, nodes) {
    const md = node.metadata || {};
    const action = String(md.action || node.kind.replace("reasoning.", "")).toUpperCase();
    return `<article class="trace-item reason"><div class="trace-rail"><span>${esc(action)}</span></div><div class="trace-card"><div class="trace-head"><strong>天策 Reasoner · ${esc(action)}</strong><span>${md.requires_human ? "需要人工" : "自治判断"}</span></div><p>${esc(node.label)}</p>${basisHtml(md.basis_fact_ids, nodes)}<div class="trace-meta"><span>next ${esc(short(md.next_step_id) || "—")}</span><span>human=${md.requires_human ? "yes" : "no"}</span></div></div></article>`;
  }

  function councilItem(node, detail, nodes) {
    const md = node.metadata || {};
    const agentEdges = edgesFrom(detail, node.id, "contains_subagent");
    const agents = agentEdges.map(edge => nodes.get(edge.target)).filter(Boolean);
    const profile = md.target_profile || {};
    return `<article class="trace-item council"><div class="trace-rail"><span>R${esc(md.round ?? "?")}</span></div><div class="trace-card"><div class="trace-head"><strong>Assessment Council · ${esc(md.focus || node.label)}</strong><span>${agents.length || md.agents || 0} agents · target ${esc(md.desired_rounds || "7–10")} rounds</span></div><div class="trace-profile-inline"><span>kind ${esc(profile.kind || "—")}</span><span>complexity ${esc(profile.complexity ?? "—")}</span><span>unknowns ${esc((profile.unknowns || []).join(" · ") || "none")}</span></div><div class="trace-agent-grid">${agents.map(agent => { const am = agent.metadata || {}; return `<div class="trace-agent"><strong>${esc(am.role || "reviewer")}</strong><span>${esc(am.focus || md.focus || "evidence review")}</span><p>${esc(am.summary || agent.label)}</p><small>${esc(am.recommended_action || "report_only")} · exec=${am.execution_authority === false ? "false" : "—"}</small></div>`; }).join("") || `<span class="trace-muted">本轮子代理详情尚未写入。</span>`}</div></div></article>`;
  }

  function stopItem(node) {
    const md = node.metadata || {};
    return `<article class="trace-item stop"><div class="trace-rail"><span>STOP</span></div><div class="trace-card"><div class="trace-head"><strong>本轮停止 · ${esc(md.reason || node.label)}</strong><span>iterations ${esc(md.iterations ?? "—")} · executions ${esc(md.executions ?? "—")}</span></div><p>停止点由预算、审批、Review、终态或证据收敛触发；不是子代理自行扩大权限。</p></div></article>`;
  }

  function reportGateItem(node) {
    const md = node.metadata || {};
    return `<article class="trace-item guard"><div class="trace-rail"><span>GATE</span></div><div class="trace-card"><div class="trace-head"><strong>REPORT_ONLY 边界</strong><span>final_active_action=false</span></div><p>${esc(node.label)}</p><div class="trace-meta"><span>payload=${md.payload_execution === false ? "blocked" : "—"}</span><span>credential=${md.credential_capture === false ? "blocked" : "—"}</span><span>session=${md.session_takeover === false ? "blocked" : "—"}</span><span>persistence=${md.persistence === false ? "blocked" : "—"}</span></div></div></article>`;
  }

  function traceTimeline(detail) {
    const nodes = nodeMap(detail);
    const relevant = (detail.graph?.nodes || []).filter(node => ["planning.revision", "council.round", "loop.stop", "governance.report_gate"].includes(node.kind) || node.kind.startsWith("reasoning."));
    const items = [seedItem(detail)];
    for (const node of relevant) {
      if (node.kind === "planning.revision") items.push(revisionItem(node, nodes));
      else if (node.kind.startsWith("reasoning.")) items.push(reasoningItem(node, nodes));
      else if (node.kind === "council.round") items.push(councilItem(node, detail, nodes));
      else if (node.kind === "loop.stop") items.push(stopItem(node));
      else if (node.kind === "governance.report_gate") items.push(reportGateItem(node));
    }
    return items.filter(Boolean).join("") || `<div class="module-empty">暂无决策轨迹。</div>`;
  }

  function renderTrace(detail) {
    return `<div class="decision-trace-shell"><div class="trace-title"><div><strong>Decision Trace · 决策轨迹</strong><span>为什么选工具、谁在分析、依据什么 Evidence、为什么继续/停止</span></div><div class="trace-legend"><span>Seed</span><span>Plan+</span><span>Reason</span><span>Council</span><span>Gate</span></div></div>${profilePanel(detail)}<div class="decision-trace-timeline">${traceTimeline(detail)}</div></div>`;
  }

  function activateTrace(tabs, content, runId) {
    tabs.querySelectorAll("[data-mission-tab]").forEach(button => button.classList.toggle("active", button.dataset.missionTab === TRACE_TAB));
    content.querySelectorAll("[data-tab-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.tabPanel === TRACE_TAB));
    sessionStorage.setItem("tonmen.trace.activeRun", runId || "");
  }

  async function installTrace() {
    if (busy || location.pathname !== "/missions") return;
    const tabs = document.querySelector("#module-page-root .mission-detail-tabs");
    const content = document.querySelector("#module-page-root .mission-tab-content");
    const runId = selectedRun();
    if (!tabs || !content || !runId) return;
    if (tabs.querySelector(`[data-mission-tab="${TRACE_TAB}"]`)) return;
    busy = true;
    try {
      const response = await fetch(`/api/missions/${encodeURIComponent(runId)}`, {cache:"no-store", headers:{"Accept":"application/json"}});
      if (!response.ok) return;
      const detail = await response.json();
      if (selectedRun() !== runId || !document.contains(tabs) || !document.contains(content)) return;
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "tab");
      button.dataset.missionTab = TRACE_TAB;
      button.textContent = "Decision Trace";
      const panel = document.createElement("section");
      panel.dataset.tabPanel = TRACE_TAB;
      panel.className = "mission-tab-panel decision-trace-panel";
      panel.innerHTML = renderTrace(detail);
      tabs.appendChild(button);
      content.appendChild(panel);
      button.addEventListener("click", event => {
        event.preventDefault();
        activateTrace(tabs, content, runId);
      });
      if (sessionStorage.getItem("tonmen.trace.activeRun") === runId) activateTrace(tabs, content, runId);
    } finally {
      busy = false;
    }
  }

  const root = document.getElementById("module-page-root");
  if (root) new MutationObserver(() => queueMicrotask(installTrace)).observe(root, {childList:true, subtree:true});
  window.addEventListener("popstate", () => setTimeout(installTrace, 0));
  window.addEventListener("tonmen:runtime-event", event => {
    const type = event.detail?.type || "";
    if (["plan.revised", "reasoning.decided", "council.round", "loop.stopped", "governance.report_gate"].includes(type)) setTimeout(installTrace, 80);
  });
  installTrace();
})();
