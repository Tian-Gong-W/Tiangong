(() => {
  "use strict";

  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const terminalLabels = new Set(["完成", "失败", "拒绝"]);

  function toast(message, bad = false) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.className = "toast"; }, 3200);
  }

  async function post(url) {
    const response = await fetch(url, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-TONMEN-CSRF": csrf,
      },
      body: "{}",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `${response.status} ${response.statusText}`);
    return payload;
  }

  function selectedRow() {
    return document.querySelector("#module-page-root .module-table tbody tr.selected[data-select-run]");
  }

  function selectedRun() {
    return new URLSearchParams(location.search).get("run") || selectedRow()?.dataset.selectRun || null;
  }

  function selectedStateLabel() {
    return selectedRow()?.querySelector(".module-badge")?.textContent?.trim() || "";
  }

  function refreshMissions(clearRun = false) {
    if (clearRun) history.replaceState({}, "", "/missions");
    const refresh = document.querySelector("#module-page-root [data-module-refresh]");
    if (refresh) refresh.click();
    else location.assign("/missions");
  }

  function syncDeleteButton(actions) {
    const button = actions.querySelector("[data-delete-selected-mission]");
    if (!button) return;
    const runId = selectedRun();
    const label = selectedStateLabel();
    button.disabled = !runId || (label && !terminalLabels.has(label));
    button.title = button.disabled && runId
      ? "运行中或候审批任务不能删除"
      : "删除当前选中的已结束任务；Audit 审计日志会保留";
  }

  function install() {
    if (location.pathname !== "/missions") return;
    const root = document.getElementById("module-page-root");
    const tools = root?.querySelector(".mission-history-tools");
    if (!tools || tools.querySelector(".mission-history-actions")) return;

    const actions = document.createElement("div");
    actions.className = "mission-history-actions";
    actions.innerHTML = `
      <button type="button" class="ghost mission-history-delete" data-delete-selected-mission>删除选中</button>
      <button type="button" class="ghost mission-history-cleanup" data-cleanup-terminal-missions>清理已结束</button>`;
    tools.appendChild(actions);
    syncDeleteButton(actions);

    actions.querySelector("[data-delete-selected-mission]")?.addEventListener("click", async () => {
      const runId = selectedRun();
      if (!runId) return;
      if (!confirm(`删除历史任务 ${runId.slice(0, 8)}？\n\n该任务的 Chronicle / Evidence / Intelligence / Reasoning 持久记录会删除；Audit 审计日志保留。`)) return;
      try {
        const payload = await post(`/api/missions/${encodeURIComponent(runId)}/delete`);
        toast(`已删除任务 ${String(payload.deleted || runId).slice(0, 8)}，剩余 ${payload.remaining ?? "?"} 条。`);
        refreshMissions(true);
      } catch (error) {
        toast(error.message || String(error), true);
      }
    });

    actions.querySelector("[data-cleanup-terminal-missions]")?.addEventListener("click", async () => {
      if (!confirm("清理所有已结束任务？\n\n只会删除完成 / 失败 / 拒绝的 Chronicle 任务记录；运行中和候审批任务会保留，Audit 审计日志也会保留。")) return;
      try {
        const payload = await post("/api/missions/cleanup");
        toast(`已清理 ${payload.count ?? 0} 条历史任务，剩余 ${payload.remaining ?? "?"} 条。`);
        refreshMissions(true);
      } catch (error) {
        toast(error.message || String(error), true);
      }
    });
  }

  const root = document.getElementById("module-page-root");
  if (root) {
    const observer = new MutationObserver(() => queueMicrotask(install));
    observer.observe(root, {childList: true, subtree: true});
  }
  document.addEventListener("click", event => {
    if (!event.target.closest?.("[data-select-run]")) return;
    setTimeout(() => {
      const actions = document.querySelector(".mission-history-actions");
      if (actions) syncDeleteButton(actions);
    }, 0);
  });
  window.addEventListener("popstate", () => setTimeout(install, 0));
  install();
})();

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

(() => {
  "use strict";

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
  const short = value => String(value || "").slice(0, 8);
  let refreshing = false;

  function selectedRun() {
    return new URLSearchParams(location.search).get("run") || document.querySelector("#module-page-root .module-table tr.selected[data-select-run]")?.dataset.selectRun || null;
  }

  function asSet(values) {
    return new Set((values || []).filter(Boolean).map(value => String(value)));
  }

  function difference(left, right) {
    return [...left].filter(value => !right.has(value));
  }

  function roundAgents(detail, roundNode, nodes) {
    const edges = (detail.graph?.edges || []).filter(edge => edge.source === roundNode.id && edge.relation === "contains_subagent");
    return edges.map(edge => nodes.get(edge.target)).filter(Boolean);
  }

  function roundFactIds(agents) {
    const ids = new Set();
    for (const agent of agents) for (const factId of agent.metadata?.fact_ids || []) ids.add(String(factId));
    return ids;
  }

  function labels(ids, nodes) {
    return ids.map(id => nodes.get(id)?.label || short(id));
  }

  function chipList(label, values, tone = "") {
    if (!values.length) return "";
    return `<div class="trace-basis"><span>${esc(label)}</span>${values.map(value => `<span class="trace-fact"${tone ? ` data-delta-tone="${tone}"` : ""}>${esc(value)}</span>`).join("")}</div>`;
  }

  function rosterReason(delta) {
    const reasons = [];
    if (delta.complexity > 0) reasons.push(`complexity +${delta.complexity}`);
    if (delta.complexity < 0) reasons.push(`complexity ${delta.complexity}`);
    if (delta.hypothesesAdded.length) reasons.push(`new hypothesis: ${delta.hypothesesAdded.join(", ")}`);
    if (delta.unknownsClosed.length) reasons.push(`unknown closed: ${delta.unknownsClosed.join(", ")}`);
    if (delta.unknownsOpened.length) reasons.push(`new unknown: ${delta.unknownsOpened.join(", ")}`);
    if (delta.newFacts.length) reasons.push(`${delta.newFacts.length} new fact(s)`);
    return reasons.join(" · ") || "profile stable; roster change is focus rotation within the bounded council";
  }

  function buildDeltas(detail) {
    const nodes = new Map((detail.graph?.nodes || []).map(node => [node.id, node]));
    const rounds = (detail.graph?.nodes || [])
      .filter(node => node.kind === "council.round")
      .slice()
      .sort((a, b) => Number(a.metadata?.round || 0) - Number(b.metadata?.round || 0));
    const deltas = [];
    let previous = {
      facts: new Set(), unknowns: new Set(), hypotheses: new Set(), roles: new Set(), complexity: 0,
    };
    for (const round of rounds) {
      const agents = roundAgents(detail, round, nodes);
      const profile = round.metadata?.target_profile || {};
      const current = {
        facts: roundFactIds(agents),
        unknowns: asSet(profile.unknowns),
        hypotheses: asSet(profile.hypotheses),
        roles: asSet(round.metadata?.roles || agents.map(agent => agent.metadata?.role)),
        complexity: Number(profile.complexity || 0),
      };
      const factIds = difference(current.facts, previous.facts);
      deltas.push({
        round: Number(round.metadata?.round || deltas.length + 1),
        focus: round.metadata?.focus || round.label,
        newFacts: labels(factIds, nodes),
        unknownsClosed: difference(previous.unknowns, current.unknowns),
        unknownsOpened: difference(current.unknowns, previous.unknowns),
        hypothesesAdded: difference(current.hypotheses, previous.hypotheses),
        hypothesesRemoved: difference(previous.hypotheses, current.hypotheses),
        rolesAdded: difference(current.roles, previous.roles),
        rolesRemoved: difference(previous.roles, current.roles),
        complexity: current.complexity - previous.complexity,
      });
      previous = current;
    }
    return deltas;
  }

  function deltaCard(delta) {
    const rosterChanged = delta.rolesAdded.length || delta.rolesRemoved.length;
    const meaningful = delta.newFacts.length || delta.unknownsClosed.length || delta.unknownsOpened.length || delta.hypothesesAdded.length || delta.hypothesesRemoved.length || delta.complexity !== 0 || rosterChanged;
    return `<article class="trace-card" style="margin-top:7px"><div class="trace-head"><strong>R${esc(delta.round)} Delta · ${esc(delta.focus)}</strong><span>${meaningful ? "profile changed" : "no material profile delta"}</span></div>
      ${chipList("New facts", delta.newFacts, "new")}
      ${chipList("Unknowns closed", delta.unknownsClosed, "closed")}
      ${chipList("Unknowns opened", delta.unknownsOpened, "opened")}
      ${chipList("Hypotheses +", delta.hypothesesAdded, "hyp-plus")}
      ${chipList("Hypotheses −", delta.hypothesesRemoved, "hyp-minus")}
      ${chipList("Agents +", delta.rolesAdded, "agent-plus")}
      ${chipList("Agents −", delta.rolesRemoved, "agent-minus")}
      <div class="trace-meta"><span>complexity Δ ${delta.complexity > 0 ? "+" : ""}${esc(delta.complexity)}</span><span>roster_changed=${rosterChanged ? "yes" : "no"}</span></div>
      ${rosterChanged ? `<div class="trace-callout"><b>为什么换 Agent</b><span>${esc(rosterReason(delta))}</span></div>` : ""}
    </article>`;
  }

  async function refreshDelta() {
    if (refreshing || location.pathname !== "/missions") return;
    const shell = document.querySelector("#module-page-root .decision-trace-shell");
    const runId = selectedRun();
    if (!shell || !runId) return;
    if (shell.querySelector(`[data-delta-run="${runId}"]`)) return;
    refreshing = true;
    try {
      const response = await fetch(`/api/missions/${encodeURIComponent(runId)}`, {cache:"no-store", headers:{"Accept":"application/json"}});
      if (!response.ok) return;
      const detail = await response.json();
      if (selectedRun() !== runId || !document.contains(shell)) return;
      const deltas = buildDeltas(detail);
      const view = document.createElement("section");
      view.dataset.deltaRun = runId;
      view.className = "trace-delta-view";
      view.innerHTML = `<div class="trace-title" style="margin-top:10px"><div><strong>Delta View · 每轮变化</strong><span>新增 Facts、关闭/新增 Unknowns、Hypothesis 与 Agent 阵容变化</span></div><div class="trace-legend"><span>${deltas.length} rounds</span><span>read only</span></div></div>${deltas.map(deltaCard).join("") || `<div class="trace-card" style="margin-top:7px"><span class="trace-muted">尚无 Council round delta。</span></div>`}`;
      const profile = shell.querySelector(".trace-profile");
      (profile || shell.querySelector(".trace-title"))?.insertAdjacentElement("afterend", view);
    } finally {
      refreshing = false;
    }
  }

  const root = document.getElementById("module-page-root");
  if (root) new MutationObserver(() => queueMicrotask(refreshDelta)).observe(root, {childList:true, subtree:true});
  window.addEventListener("popstate", () => setTimeout(refreshDelta, 0));
  window.addEventListener("tonmen:runtime-event", event => {
    if (["intelligence.created", "plan.revised", "council.round", "reasoning.decided", "loop.stopped"].includes(event.detail?.type || "")) {
      document.querySelector(".trace-delta-view")?.remove();
      setTimeout(refreshDelta, 100);
    }
  });
  refreshDelta();
})();
