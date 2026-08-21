(() => {
  "use strict";

  const root = document.getElementById("module-page-root");
  if (!root) return;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
  const severityNames = {critical:"严重", high:"高", medium:"中", low:"低", info:"信息", unknown:"未知"};
  const stateNames = {pending:"待执行", running:"执行中", waiting_approval:"等待批准", succeeded:"已完成", degraded:"部分完成", skipped:"已跳过", failed:"失败", denied:"已拒绝"};
  const evidenceNames = {confirmed:"证据确认", observed:"已观察", matched_only:"仅模板命中", not_confirmed:"未确认"};
  const attributionNames = {supported:"归因支持", contradicted:"归因冲突", unverified:"未验证", mixed:"混合", not_applicable:"不适用"};
  const assetKinds = {host:"目标", ip:"IP", backend:"后端", service:"服务", web:"网站", finding:"漏洞"};
  const coverageNames = {scanned:"已扫描", planned:"已计划", authorized_uncovered:"已授权未覆盖", needs_scope:"需要授权", observed:"已观察", not_scanned:"未扫描"};
  const tone = value => ["critical","high","contradicted","failed","denied","needs_scope","not_confirmed"].includes(value) ? "bad" : ["medium","mixed","unverified","matched_only","waiting_approval","running","authorized_uncovered","observed","not_scanned"].includes(value) ? "warn" : ["confirmed","supported","succeeded","scanned"].includes(value) ? "ok" : "blue";

  const selectedRun = () => new URLSearchParams(location.search).get("run") || root.querySelector("tr.selected[data-select-run]")?.dataset.selectRun || null;

  async function mission(id) {
    const response = await fetch(`/api/missions/${encodeURIComponent(id)}`, {cache:"no-store"});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data;
  }

  function findDetailBody() {
    const cards = [...root.querySelectorAll(".module-card")];
    const card = cards.find(item => item.querySelector(".module-card-head h2")?.textContent?.includes("任务详情"));
    return card?.querySelector(".module-card-body") || null;
  }

  function badge(text, value = "") {
    return `<span class="module-badge ${tone(value)}">${esc(text)}</span>`;
  }

  function trailView(workspace) {
    const data = workspace.exploration || {};
    const nodes = data.nodes || [];
    const edges = data.edges || [];
    const byId = Object.fromEntries(nodes.map(node => [node.id, node]));
    const intents = nodes.filter(node => node.kind === "intent").sort((a,b) => Number(a.order || 0) - Number(b.order || 0));
    const goal = nodes.find(node => node.kind === "goal");
    const children = source => edges.filter(edge => edge.source === source).map(edge => ({edge, node:byId[edge.target]})).filter(item => item.node);
    const incoming = target => edges.filter(edge => edge.target === target).map(edge => ({edge, node:byId[edge.source]})).filter(item => item.node);

    const intentHtml = intents.map((intent, index) => {
      const facts = children(intent.id).filter(item => item.node.kind === "fact");
      const findings = children(intent.id).filter(item => item.node.kind === "finding");
      const reasons = incoming(intent.id).filter(item => item.node.kind === "decision");
      return `<article class="mission-trail-step">
        <div class="mission-trail-index">${index + 1}</div>
        <div class="mission-trail-content">
          ${reasons.map(item => `<div class="mission-trail-reason"><span>为什么继续</span><strong>${esc(item.node.title)}</strong></div>`).join("")}
          <div class="mission-intent-head"><div><strong>${esc(intent.title)}</strong><code>${esc(intent.target || "")}</code></div>${badge(stateNames[intent.state] || intent.state, intent.state)}</div>
          ${intent.detail ? `<p>${esc(intent.detail)}</p>` : ""}
          ${intent.requires_approval ? `<div class="mission-approval-note">这一步需要人工确认。</div>` : ""}
          ${facts.length ? `<div class="mission-trail-facts">${facts.map(item => `<div class="mission-fact"><span>${esc(item.node.fact_kind || "事实")}</span><strong>${esc(item.node.title)}</strong>${item.node.severity && item.node.severity !== "info" ? badge(severityNames[item.node.severity] || item.node.severity, item.node.severity) : ""}</div>`).join("")}</div>` : `<div class="mission-trail-empty">暂无新事实</div>`}
          ${findings.map(item => `<div class="mission-trail-finding"><span>确认漏洞</span><strong>${esc(item.node.title)}</strong>${badge(severityNames[item.node.severity] || item.node.severity, item.node.severity)}</div>`).join("")}
        </div>
      </article>`;
    }).join("");

    const goalFindings = goal ? children(goal.id).filter(item => item.node.kind === "finding") : [];
    return `<div class="mission-workspace-summary"><div><span>探索方向</span><strong>${data.counts?.intents || 0}</strong></div><div><span>事实</span><strong>${data.counts?.facts || 0}</strong></div><div><span>判断</span><strong>${data.counts?.decisions || 0}</strong></div><div><span>漏洞</span><strong>${data.counts?.findings || 0}</strong></div></div>
      <div class="mission-goal"><span>任务目标</span><strong>${esc(goal?.title || "—")}</strong></div>
      <div class="mission-trail">${intentHtml || `<div class="mission-trail-empty">暂无探索步骤</div>`}</div>
      ${goalFindings.map(item => `<div class="mission-trail-finding"><span>任务级漏洞</span><strong>${esc(item.node.title)}</strong></div>`).join("")}`;
  }

  function findingsView(workspace) {
    const findings = workspace.findings || [];
    if (!findings.length) return `<div class="mission-workspace-empty"><strong>暂未确认漏洞</strong><span>有证据支持的漏洞会显示在这里。</span></div>`;
    return `<div class="mission-finding-list">${findings.map(item => {
      const backends = item.affected_backends || [];
      return `<article class="mission-finding-card">
        <div class="mission-finding-head"><div><strong>${esc(item.name || item.template_id || "漏洞")}</strong><small>${esc(item.template_id || item.identity || "")}</small></div>${badge(severityNames[item.severity] || item.severity, item.severity)}</div>
        <div class="mission-finding-status">${badge(evidenceNames[item.evidence_status] || item.evidence_status, item.evidence_status)}${badge(attributionNames[item.attribution_status] || item.attribution_status, item.attribution_status)}<span>置信度 ${esc(item.confidence ?? "—")}</span></div>
        <div class="mission-finding-backends"><span>影响资产</span>${backends.length ? backends.map(backend => `<code>${esc(backend.backend)} · ${esc(evidenceNames[backend.evidence_status] || backend.evidence_status)}</code>`).join("") : `<code>未定位具体后端</code>`}</div>
        <details><summary>证据关系</summary><div>证据 ${esc((item.evidence_ids || []).map(id => String(id).slice(0,8)).join(", ") || "—")} · 命中 ${esc(item.instance_count || 0)} 次 · 后端 ${esc(item.unique_backend_count || 0)} 个</div></details>
      </article>`;
    }).join("")}</div>`;
  }

  function assetMeta(node) {
    if (node.kind === "ip" || node.kind === "backend") {
      const scope = node.scope_status === "authorized" ? "已授权" : node.scope_status === "needs_scope" ? "需要授权" : "仅观察";
      return `${scope}${node.coverage_status ? ` · ${coverageNames[node.coverage_status] || node.coverage_status}` : ""}`;
    }
    if (node.kind === "service") return node.detail || "已发现服务";
    if (node.kind === "web") return [node.status_code, node.title].filter(value => value !== null && value !== undefined && value !== "").join(" · ") || "网站入口";
    if (node.kind === "finding") return `${severityNames[node.severity] || node.severity || "未知"} · ${evidenceNames[node.evidence_status] || node.evidence_status || "未确认"}`;
    return "任务目标";
  }

  function assetsView(workspace) {
    const graph = workspace.assets || {};
    const nodes = graph.nodes || [];
    const edges = graph.edges || [];
    const byId = Object.fromEntries(nodes.map(node => [node.id, node]));
    const children = {};
    for (const edge of edges) (children[edge.source] ||= []).push({edge, node:byId[edge.target]});

    function renderNode(id, depth = 0, path = new Set()) {
      const node = byId[id];
      if (!node || path.has(id) || depth > 5) return "";
      const nextPath = new Set(path); nextPath.add(id);
      const childHtml = (children[id] || []).map(item => `<div class="mission-asset-branch"><span class="mission-asset-relation">${esc(item.edge.relation)}</span>${renderNode(item.node.id, depth + 1, nextPath)}</div>`).join("");
      return `<div class="mission-asset-tree-node" data-kind="${esc(node.kind)}"><div class="mission-asset-node-card"><span>${esc(assetKinds[node.kind] || node.kind)}</span><strong>${esc(node.title)}</strong><small>${esc(assetMeta(node))}</small></div>${childHtml ? `<div class="mission-asset-children">${childHtml}</div>` : ""}</div>`;
    }

    const summary = graph.summary || {};
    return `<div class="mission-workspace-summary"><div><span>资产</span><strong>${summary.assets || 0}</strong></div><div><span>解析地址</span><strong>${summary.resolved_addresses || 0}</strong></div><div><span>已扫描地址</span><strong>${summary.scanned_addresses || 0}</strong></div><div><span>需要授权</span><strong>${summary.needs_scope || 0}</strong></div></div>
      <div class="mission-asset-tree">${renderNode(graph.root_id) || `<div class="mission-workspace-empty">暂无资产关系</div>`}</div>
      <div class="mission-asset-note">DNS 解析只记录资产，不会自动扩大授权范围。漏洞只绑定到已有证据支持的资产。</div>`;
  }

  function reportView(workspace, runId) {
    const report = workspace.report || {};
    const summary = report.summary || {};
    return `<div class="mission-workspace-summary"><div><span>报告</span><strong>${report.type === "final" ? "最终" : "进行中"}</strong></div><div><span>漏洞</span><strong>${summary.unique_findings || 0}</strong></div><div><span>证据</span><strong>${summary.evidence_records || 0}</strong></div><div><span>影响后端</span><strong>${summary.affected_backends || 0}</strong></div></div>
      <div class="mission-report-short"><strong>完整报告保留原始证据、请求响应、AI 评审和治理记录。</strong><button type="button" class="primary" data-workspace-report="${esc(runId)}">查看完整报告</button></div>`;
  }

  function renderWorkspace(body, data) {
    const workspace = data.workspace;
    if (!workspace) return;
    const runId = data.id;
    body.dataset.missionWorkspaceFor = runId;
    body.innerHTML = `<div class="mission-workspace-head"><div><strong>${esc(data.target)}</strong><span>${esc(stateNames[data.state] || data.state)}</span></div><small>任务内视图</small></div>
      <div class="mission-workspace-tabs" role="tablist"><button class="active" data-workspace-tab="exploration">探索链</button><button data-workspace-tab="findings">漏洞 <b>${workspace.findings?.length || 0}</b></button><button data-workspace-tab="assets">资产</button><button data-workspace-tab="report">报告</button></div>
      <div class="mission-workspace-panel" data-workspace-panel></div>`;

    const panel = body.querySelector("[data-workspace-panel]");
    const renderTab = name => {
      body.querySelectorAll("[data-workspace-tab]").forEach(button => button.classList.toggle("active", button.dataset.workspaceTab === name));
      if (name === "exploration") panel.innerHTML = trailView(workspace);
      else if (name === "findings") panel.innerHTML = findingsView(workspace);
      else if (name === "assets") panel.innerHTML = assetsView(workspace);
      else panel.innerHTML = reportView(workspace, runId);
      panel.querySelector("[data-workspace-report]")?.addEventListener("click", () => {
        const button = document.querySelector("[data-open-full-report]");
        if (button) button.click();
      });
    };
    body.querySelectorAll("[data-workspace-tab]").forEach(button => button.addEventListener("click", () => renderTab(button.dataset.workspaceTab)));
    renderTab("exploration");
  }

  const inflight = new Set();
  async function apply() {
    if ((location.pathname.replace(/\/+$/, "") || "/") !== "/missions") return;
    const body = findDetailBody();
    const runId = selectedRun();
    if (!body || !runId || body.dataset.missionWorkspaceFor === runId || inflight.has(runId)) return;
    inflight.add(runId);
    try {
      const data = await mission(runId);
      if (!body.isConnected || selectedRun() !== runId) return;
      renderWorkspace(body, data);
    } catch (_) {
      // Keep the existing Mission detail view if the projection cannot be loaded.
    } finally {
      inflight.delete(runId);
    }
  }

  new MutationObserver(() => queueMicrotask(apply)).observe(root, {childList:true, subtree:true});
  window.addEventListener("popstate", () => setTimeout(apply, 20));
  window.addEventListener("tonmen:runtime-event", () => setTimeout(apply, 80));
  setTimeout(apply, 20);
})();
