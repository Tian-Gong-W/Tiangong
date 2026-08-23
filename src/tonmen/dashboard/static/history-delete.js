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

(() => {
  "use strict";
  const WHY_GRAPH_PLUGIN = true;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;'"}[ch]));
  const short = value => String(value || "").slice(0, 8);
  let installing = false;
  let cachedDetail = null;
  let cachedRunId = null;

  function selectedRun() {
    return new URLSearchParams(location.search).get("run") || document.querySelector("#module-page-root .module-table tr.selected[data-select-run]")?.dataset.selectRun || null;
  }

  function ensureStyles() {
    if (document.getElementById("tonmen-why-graph-style")) return;
    const style = document.createElement("style");
    style.id = "tonmen-why-graph-style";
    style.textContent = `
      .why-graph-view{margin-top:10px}.why-toolbar{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.why-tool{min-height:30px;padding:5px 9px;border:1px solid #315365;border-radius:6px;background:#07131b;color:#91b2c1;font-size:9px;cursor:pointer}.why-tool:hover,.why-tool.active{border-color:#68a9c5;color:#d8edf5;background:#0b1d28}.why-chain{display:grid;grid-template-columns:minmax(120px,1fr) 24px minmax(140px,1.2fr) 24px minmax(170px,1.25fr) 24px minmax(160px,1.15fr) 24px minmax(130px,1fr);gap:6px;align-items:stretch;margin-top:9px}.why-lane{min-width:0;padding:8px;border:1px solid #203846;border-radius:7px;background:#08151e}.why-lane>span{display:block;margin-bottom:6px;color:#637d8a;font-size:8px;text-transform:uppercase;letter-spacing:.06em}.why-node{padding:7px;border:1px solid #2a4858;border-radius:5px;background:#07131b;margin-top:5px;min-width:0}.why-node:first-of-type{margin-top:0}.why-node strong{display:block;color:#cfe0e7;font-size:9px;overflow:hidden;text-overflow:ellipsis}.why-node small{display:block;margin-top:3px;color:#718995;font-size:8px;line-height:1.4;overflow-wrap:anywhere}.why-node.fact{border-color:#355a6e}.why-node.reason{border-color:#725b33}.why-node.council{border-color:#5d4977}.why-node.revision{border-color:#3c7388}.why-node.tool{border-color:#3d745d}.why-arrow{display:grid;place-items:center;color:#4e7486;font-size:16px}.why-summary{margin-top:9px;padding:8px 10px;border-left:2px solid #4f8aa1;background:#07131b;color:#9fb9c5;font-size:9px;line-height:1.55}.why-step-button{min-height:24px;padding:3px 7px;margin-left:7px;border:1px solid #3b6578;border-radius:5px;background:#07131b;color:#83bdd0;font-size:8px;cursor:pointer}.why-step-button:hover{border-color:#6eb3d0;color:#d7f2fb}@media(max-width:980px){.why-chain{grid-template-columns:1fr}.why-arrow{transform:rotate(90deg);min-height:20px}}
    `;
    document.head.appendChild(style);
  }

  function nodeMap(detail) {
    return new Map((detail.graph?.nodes || []).map(node => [node.id, node]));
  }

  function overlaps(left, right) {
    const set = new Set(left || []);
    return (right || []).some(value => set.has(value));
  }

  function revisionForStep(step, nodes) {
    const id = step?.metadata?.plan_revision_id;
    if (id && nodes.has(id)) return nodes.get(id);
    return [...nodes.values()].find(node => node.kind === "planning.revision" && node.metadata?.tool === step.tool) || null;
  }

  function evidenceForFacts(detail, basisIds) {
    const wanted = new Set(basisIds || []);
    const evidenceIds = [];
    for (const edge of detail.graph?.edges || []) {
      if (edge.relation === "reveals" && wanted.has(edge.target) && !evidenceIds.includes(edge.source)) evidenceIds.push(edge.source);
    }
    return evidenceIds.map(id => (detail.evidence || []).find(item => item.id === id)).filter(Boolean);
  }

  function reasoningForStep(detail, step, basisIds) {
    return (detail.reasoning || []).filter(node => {
      const md = node.metadata || {};
      return md.next_step_id === step.id || overlaps(basisIds, md.basis_fact_ids || []);
    });
  }

  function councilForFacts(detail, basisIds, reasoningIds, nodes) {
    const reasoningSet = new Set(reasoningIds || []);
    const basis = new Set(basisIds || []);
    return (detail.graph?.nodes || []).filter(round => {
      if (round.kind !== "council.round") return false;
      if (reasoningSet.has(round.metadata?.decision_id)) return true;
      const agents = (detail.graph?.edges || [])
        .filter(edge => edge.source === round.id && edge.relation === "contains_subagent")
        .map(edge => nodes.get(edge.target)).filter(Boolean);
      return agents.some(agent => (agent.metadata?.fact_ids || []).some(id => basis.has(id)));
    });
  }

  function whyModels(detail) {
    const nodes = nodeMap(detail);
    return (detail.steps || []).filter(step => step.metadata?.plan_revision_id).map(step => {
      const revision = revisionForStep(step, nodes);
      const basisIds = revision?.metadata?.basis_fact_ids || step.metadata?.basis_fact_ids || [];
      const facts = basisIds.map(id => nodes.get(id)).filter(Boolean);
      const evidence = evidenceForFacts(detail, basisIds);
      const reasoning = reasoningForStep(detail, step, basisIds);
      const council = councilForFacts(detail, basisIds, reasoning.map(node => node.id), nodes);
      const profile = step.metadata?.adaptive_profile || {};
      const revisionEdge = (detail.graph?.edges || []).find(edge => edge.source === revision?.id && edge.relation === "adds_step" && edge.target === step.id);
      const supportEdges = (detail.graph?.edges || []).filter(edge => edge.target === revision?.id && edge.relation === "supports_plan_revision");
      return {step, revision, basisIds, facts, evidence, reasoning, council, profile, revisionEdge, supportEdges};
    });
  }

  function lane(title, items, kind, formatter) {
    const content = items.length ? items.map(item => `<div class="why-node ${kind}">${formatter(item)}</div>`).join("") : `<div class="why-node"><small>none recorded</small></div>`;
    return `<section class="why-lane"><span>${esc(title)}</span>${content}</section>`;
  }

  function renderModel(model) {
    const md = model.revision?.metadata || {};
    const evidenceLane = lane("Evidence", model.evidence, "evidence", item => `<strong>${esc(item.tool)} · ${esc(short(item.id))}</strong><small>exit ${esc(item.exit_code)} · $ ${esc((item.argv || []).join(" "))}</small>`);
    const factLane = lane("Facts", model.facts, "fact", item => `<strong>${esc(item.label)}</strong><small>${esc(item.kind)} · ${esc(short(item.id))}</small>`);
    const contextItems = [
      ...model.reasoning.map(item => ({kind:"reason", title:`Reasoner · ${item.metadata?.action || item.kind}`, text:item.label})),
      ...model.council.map(item => ({kind:"council", title:`Council R${item.metadata?.round ?? "?"} · ${item.metadata?.focus || "review"}`, text:`${(item.metadata?.roles || []).join(", ") || "evidence review"}`})),
      {kind:"profile", title:`Profile · complexity ${model.profile.complexity ?? "—"}`, text:`unknowns: ${(model.profile.unknowns || []).join(", ") || "none"} · hypotheses: ${(model.profile.hypotheses || []).join(", ") || "none"}`},
    ];
    const contextLane = lane("Context / judgment", contextItems, "", item => `<strong>${esc(item.title)}</strong><small>${esc(item.text)}</small>`);
    const revisionLane = lane("Plan revision", model.revision ? [model.revision] : [], "revision", item => `<strong>${esc(item.label)}</strong><small>${esc(md.rationale || "—")}</small><small>information gain: ${esc(md.expected_information_gain || "—")}</small><small>support edges ${model.supportEdges.length} · adds_step=${model.revisionEdge ? "yes" : "no"} · execution_authority=${md.execution_authority === false ? "false" : "—"}</small>`);
    const toolLane = lane("Selected tool", [model.step], "tool", item => `<strong>${esc(item.tool)}</strong><small>${esc(item.target)} · L${esc(item.risk ?? "—")} · ${item.requires_approval ? "approval" : "governed auto"}</small>`);
    return `<div class="why-chain">${evidenceLane}<div class="why-arrow">→</div>${factLane}<div class="why-arrow">→</div>${contextLane}<div class="why-arrow">→</div>${revisionLane}<div class="why-arrow">→</div>${toolLane}</div><div class="why-summary"><strong>Why selected:</strong> ${esc(md.rationale || model.step.metadata?.plan_rationale || "The recorded evidence basis justified this registered capability.")}<br><strong>Basis:</strong> ${model.facts.length} Fact(s) from ${model.evidence.length} Evidence record(s). The graph contains ${model.supportEdges.length} <code>supports_plan_revision</code> edge(s) and ${model.revisionEdge ? "an" : "no"} <code>adds_step</code> edge.</div>`;
  }

  function renderWhyGraph(view, models, selectedStepId) {
    const selected = models.find(model => model.step.id === selectedStepId) || models[0];
    view.innerHTML = `<div class="trace-title"><div><strong>Why Graph · 为什么选这个工具</strong><span>Evidence → Fact → Profile / Reasoner / Council → planning.revision → Dynamic Tool</span></div><div class="trace-legend"><span>${models.length} dynamic tools</span><span>read only</span></div></div><div class="why-toolbar">${models.map(model => `<button type="button" class="why-tool ${selected?.step.id === model.step.id ? "active" : ""}" data-why-select-step="${esc(model.step.id)}">${esc(model.step.tool)} · ${esc(short(model.revision?.id))}</button>`).join("")}</div>${selected ? renderModel(selected) : `<div class="trace-card" style="margin-top:8px"><span class="trace-muted">尚无 Evidence-driven dynamic capability。</span></div>`}`;
    view.dataset.selectedStep = selected?.step.id || "";
  }

  function installExecutionButtons(detail, models) {
    const cards = [...document.querySelectorAll("#module-page-root .trace-execution-delta-view > .trace-card")];
    const executed = (detail.steps || []).filter(step => step.evidence_id);
    cards.forEach((card, index) => {
      const step = executed[index];
      if (!step?.metadata?.plan_revision_id || card.querySelector("[data-open-why-step]")) return;
      const model = models.find(item => item.step.id === step.id);
      if (!model) return;
      const head = card.querySelector(".trace-head");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "why-step-button";
      button.dataset.openWhyStep = step.id;
      button.textContent = "Why?";
      head?.appendChild(button);
    });
  }

  async function installWhyGraph() {
    if (installing || location.pathname !== "/missions") return;
    ensureStyles();
    const shell = document.querySelector("#module-page-root .decision-trace-shell");
    const runId = selectedRun();
    if (!shell || !runId) return;
    installing = true;
    try {
      let detail = cachedRunId === runId ? cachedDetail : null;
      if (!detail) {
        const response = await fetch(`/api/missions/${encodeURIComponent(runId)}`, {cache:"no-store", headers:{"Accept":"application/json"}});
        if (!response.ok) return;
        detail = await response.json();
        cachedRunId = runId;
        cachedDetail = detail;
      }
      if (selectedRun() !== runId || !document.contains(shell)) return;
      const models = whyModels(detail);
      let view = shell.querySelector(`[data-why-graph-run="${runId}"]`);
      if (!view) {
        view = document.createElement("section");
        view.className = "why-graph-view";
        view.dataset.whyGraphRun = runId;
        const executionDelta = shell.querySelector(".trace-execution-delta-view");
        const councilDelta = shell.querySelector(".trace-delta-view");
        if (executionDelta) executionDelta.insertAdjacentElement("afterend", view);
        else if (councilDelta) councilDelta.insertAdjacentElement("afterend", view);
        else (shell.querySelector(".trace-profile") || shell.querySelector(".trace-title"))?.insertAdjacentElement("afterend", view);
      }
      renderWhyGraph(view, models, view.dataset.selectedStep || models[0]?.step.id);
      installExecutionButtons(detail, models);
    } finally {
      installing = false;
    }
  }

  document.addEventListener("click", event => {
    const direct = event.target.closest?.("[data-open-why-step]");
    const select = event.target.closest?.("[data-why-select-step]");
    const stepId = direct?.dataset.openWhyStep || select?.dataset.whySelectStep;
    if (!stepId) return;
    const view = document.querySelector("#module-page-root .why-graph-view");
    if (!view || !cachedDetail) return;
    const models = whyModels(cachedDetail);
    renderWhyGraph(view, models, stepId);
    view.scrollIntoView({behavior:"smooth", block:"start"});
  });

  const root = document.getElementById("module-page-root");
  if (root) new MutationObserver(() => queueMicrotask(installWhyGraph)).observe(root, {childList:true, subtree:true});
  window.addEventListener("popstate", () => { cachedDetail = null; cachedRunId = null; setTimeout(installWhyGraph, 0); });
  window.addEventListener("tonmen:runtime-event", event => {
    if (["step.completed", "intelligence.created", "plan.revised", "reasoning.decided", "council.round", "loop.stopped"].includes(event.detail?.type || "")) {
      cachedDetail = null;
      cachedRunId = null;
      document.querySelector("#module-page-root .why-graph-view")?.remove();
      setTimeout(installWhyGraph, 140);
    }
  });
  installWhyGraph();
})();
