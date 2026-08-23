(() => {
  "use strict";

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
  const short = value => String(value || "").slice(0, 8);

  function toast(message, bad = false) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.className = "toast"; }, 3600);
  }

  function selectedRun() {
    return new URLSearchParams(location.search).get("run") ||
      document.querySelector("#module-page-root tr.selected[data-select-run]")?.dataset.selectRun ||
      document.getElementById("mission-select")?.value || null;
  }

  function ensureDialog() {
    let dialog = document.getElementById("mission-report-dialog");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "mission-report-dialog";
    dialog.className = "mission-report-dialog";
    dialog.innerHTML = `
      <div class="report-shell">
        <div class="report-head">
          <div><span>FINAL / INTERIM ARTIFACT</span><h2>完整执行报告 / Mission Report</h2><small id="report-subtitle">读取中…</small></div>
          <button type="button" class="ghost" data-report-close>×</button>
        </div>
        <div class="report-actions">
          <button type="button" class="primary" data-report-download-json>下载 JSON</button>
          <button type="button" class="ghost" data-report-download-md>下载 Markdown</button>
          <button type="button" class="ghost" data-report-copy-summary>复制摘要</button>
        </div>
        <div id="report-body" class="report-body"><div class="module-empty">正在生成报告…</div></div>
      </div>`;
    document.body.appendChild(dialog);
    dialog.querySelector("[data-report-close]")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
    return dialog;
  }

  function downloadText(filename, text, type) {
    const blob = new Blob([text], {type});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function payloadBlock(item, index) {
    return `<details class="report-payload" ${index === 0 ? "open" : ""}>
      <summary><strong>${esc(item.template_id || item.name || `Payload ${index + 1}`)}</strong><span>${esc(item.severity || "unknown")}</span><code>${esc(item.matched_at || "")}</code></summary>
      <div class="report-kv"><span>Template</span><code>${esc(item.template_path || item.template || "—")}</code><span>Host / IP</span><code>${esc(item.host || "—")} / ${esc(item.ip || "—")}</code><span>Matcher</span><code>${esc(item.matcher_status)}</code></div>
      <h4>Executed request / payload</h4><pre>${esc(item.request || "(not captured)")}</pre>
      <h4>Response</h4><pre>${esc(item.response || "(not captured)")}</pre>
    </details>`;
  }

  function reportHtml(report) {
    const mission = report.mission || {};
    const summary = report.summary || {};
    const findings = report.findings || [];
    const rounds = report.assessment_council || [];
    const payloads = report.executed_payloads || [];
    const steps = report.steps || [];
    const evidence = report.evidence || [];
    const reasoning = report.reasoning || [];

    const findingHtml = findings.length ? findings.map(item => {
      const md = item.metadata || {};
      return `<article class="report-finding"><div><strong>${esc(item.label)}</strong><span class="module-badge ${["critical","high"].includes(md.severity) ? "bad" : md.severity === "medium" ? "warn" : "blue"}">${esc(md.severity || "unknown")}</span></div><small>Evidence ${esc(short(md.evidence_id))} · ${esc(md.target || mission.target || "")}</small><code>${esc(JSON.stringify(md.data || {}))}</code></article>`;
    }).join("") : `<div class="module-empty">没有 Evidence-backed Finding。</div>`;

    const stepHtml = steps.map((step, index) => `<tr><td>${index + 1}</td><td>${esc(step.tool)}</td><td>${esc(step.target)}</td><td>L${esc(step.risk)}</td><td>${step.requires_approval ? "yes" : "no"}</td><td>${esc(step.state)}</td><td>${esc(step.metadata?.exit_code ?? "—")}</td></tr>`).join("");

    const councilHtml = rounds.map(round => {
      const md = round.metadata || {};
      const agents = (round.subagents || []).map(agent => {
        const am = agent.metadata || {};
        return `<li><strong>${esc(am.role)}</strong><span>${esc(am.summary || agent.label)}</span><code>${esc(am.recommended_action || "")}</code></li>`;
      }).join("");
      return `<details class="report-round"><summary>Round ${esc(md.round)} · ${esc(md.focus)} <span>${esc(md.phase)} · ${(round.subagents || []).length} agents</span></summary><ul>${agents}</ul></details>`;
    }).join("");

    const evidenceHtml = evidence.map(item => `<details class="report-evidence"><summary><strong>${esc(item.tool)}</strong><code>${esc(short(item.id))}</code><span>exit ${esc(item.exit_code)}</span></summary><div class="report-command">$ ${esc((item.argv || []).join(" "))}</div><h4>stdout</h4><pre>${esc(item.stdout || "(empty)")}</pre><h4>stderr</h4><pre>${esc(item.stderr || "(empty)")}</pre></details>`).join("");

    const reasoningHtml = reasoning.slice().reverse().map(item => `<div class="report-reason"><strong>${esc(item.metadata?.action || item.kind)}</strong><span>${esc(item.label)}</span><small>facts ${(item.metadata?.basis_fact_ids || []).length} · human ${item.metadata?.requires_human ? "yes" : "no"}</small></div>`).join("");

    return `<section class="report-summary">
      <div><span>Target</span><strong>${esc(mission.target)}</strong></div><div><span>State</span><strong>${esc(mission.state)}</strong></div><div><span>Report</span><strong>${esc(report.report_type)}</strong></div><div><span>Steps</span><strong>${summary.steps || 0}</strong></div><div><span>Findings</span><strong>${summary.findings || 0}</strong></div><div><span>Payloads</span><strong>${summary.executed_payloads || 0}</strong></div><div><span>Rounds</span><strong>${summary.assessment_rounds || 0}</strong></div><div><span>Subagent reviews</span><strong>${summary.subagent_reviews || 0}</strong></div>
    </section>
    <section class="report-section"><h3>治理 / Governance</h3><p>${esc(report.governance?.execution_model || "")}</p><div class="report-governance">Assessment target: ${esc(report.governance?.policy?.assessment_rounds || 8)} rounds · ${esc(report.governance?.policy?.subagents_per_round || 4)} subagents/round · approval tokens persisted: no · arbitrary shell: disabled</div></section>
    <section class="report-section"><h3>执行步骤 / Steps</h3><div class="module-table-wrap"><table class="module-table"><thead><tr><th>#</th><th>Tool</th><th>Target</th><th>Risk</th><th>Approval</th><th>State</th><th>Exit</th></tr></thead><tbody>${stepHtml}</tbody></table></div></section>
    <section class="report-section"><h3>漏洞与事实 / Findings</h3>${findingHtml}</section>
    <section class="report-section"><h3>已执行 Payload / Request / Response</h3>${payloads.length ? payloads.map(payloadBlock).join("") : `<div class="module-empty">当前报告没有结构化 Nuclei request/response payload。</div>`}</section>
    <section class="report-section"><h3>Assessment Council · 7–10 rounds</h3>${councilHtml || `<div class="module-empty">Council 尚未产生轮次。</div>`}</section>
    <section class="report-section"><h3>Reasoning</h3>${reasoningHtml || `<div class="module-empty">暂无 Reasoning。</div>`}</section>
    <section class="report-section"><h3>Raw Evidence</h3>${evidenceHtml || `<div class="module-empty">暂无 Evidence。</div>`}</section>`;
  }

  async function openReport(runId, {auto = false} = {}) {
    if (!runId) return;
    const dialog = ensureDialog();
    const body = dialog.querySelector("#report-body");
    body.innerHTML = `<div class="module-empty">正在读取完整报告…</div>`;
    if (!dialog.open) dialog.showModal();
    try {
      const response = await fetch(`/api/missions/${encodeURIComponent(runId)}/report`, {cache:"no-store", headers:{"Accept":"application/json"}});
      const report = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(report.error || `${response.status} ${response.statusText}`);
      dialog.dataset.runId = runId;
      dialog.dataset.reportJson = JSON.stringify(report, null, 2);
      dialog.querySelector("#report-subtitle").textContent = `${report.mission?.target || ""} · ${runId} · ${report.report_type || "report"}`;
      body.innerHTML = reportHtml(report);

      dialog.querySelector("[data-report-download-json]").onclick = () => downloadText(`tonmen-${runId}-report.json`, dialog.dataset.reportJson || "{}", "application/json;charset=utf-8");
      dialog.querySelector("[data-report-download-md]").onclick = async () => {
        try {
          const md = await fetch(`/api/missions/${encodeURIComponent(runId)}/report?format=markdown`, {cache:"no-store"});
          if (!md.ok) throw new Error(`${md.status} ${md.statusText}`);
          downloadText(`tonmen-${runId}-report.md`, await md.text(), "text/markdown;charset=utf-8");
        } catch (error) { toast(error.message || String(error), true); }
      };
      dialog.querySelector("[data-report-copy-summary]").onclick = async () => {
        const summary = `${report.mission?.target || ""} · ${report.mission?.state || ""} · ${report.summary?.findings || 0} findings · ${report.summary?.executed_payloads || 0} payloads · ${report.summary?.assessment_rounds || 0} rounds · ${report.summary?.subagent_reviews || 0} subagent reviews`;
        try { await navigator.clipboard.writeText(summary); toast("报告摘要已复制"); }
        catch (_) { window.prompt("复制报告摘要", summary); }
      };
      if (auto) toast(`任务执行结束：完整报告已生成（${report.summary?.assessment_rounds || 0} 轮 / ${report.summary?.subagent_reviews || 0} 子代理复核）`);
    } catch (error) {
      body.innerHTML = `<div class="module-error">${esc(error.message || error)}</div>`;
    }
  }

  function installReportButton() {
    if (location.pathname !== "/missions") return;
    const toolbar = document.querySelector("#module-page-root .module-toolbar");
    if (!toolbar || toolbar.querySelector("[data-open-full-report]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost";
    button.dataset.openFullReport = "";
    button.textContent = "▤ 完整报告";
    button.addEventListener("click", () => openReport(selectedRun()));
    toolbar.appendChild(button);
  }

  window.addEventListener("tonmen:runtime-event", event => {
    const runtime = event.detail || {};
    if (runtime.type !== "report.ready") return;
    const runId = runtime.data?.mission_id;
    if (!runId) return;
    const key = `tonmen.report.shown.${runId}`;
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
    openReport(runId, {auto:true});
  });

  const root = document.getElementById("module-page-root");
  if (root) new MutationObserver(() => queueMicrotask(installReportButton)).observe(root, {childList:true, subtree:true});
  window.addEventListener("popstate", () => setTimeout(installReportButton, 0));
  setTimeout(installReportButton, 0);
})();

(() => {
  "use strict";

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
  const short = value => String(value || "").slice(0, 8);
  let refreshing = false;

  function selectedRun() {
    return new URLSearchParams(location.search).get("run") ||
      document.querySelector("#module-page-root tr.selected[data-select-run]")?.dataset.selectRun || null;
  }

  function nodeMap(detail) {
    return new Map((detail.graph?.nodes || []).map(node => [node.id, node]));
  }

  function difference(left, right) {
    const r = new Set(right || []);
    return [...new Set(left || [])].filter(value => !r.has(value));
  }

  function factNodesForEvidence(detail, evidenceId, nodes) {
    return (detail.graph?.edges || [])
      .filter(edge => edge.source === evidenceId && edge.relation === "reveals")
      .map(edge => nodes.get(edge.target)).filter(Boolean);
  }

  function profile(step) {
    const value = step?.metadata?.adaptive_profile || {};
    return {
      complexity: Number(value.complexity || 0),
      unknowns: value.unknowns || [],
      hypotheses: value.hypotheses || [],
    };
  }

  function revisionTriggeredBy(detail, factIds) {
    const facts = new Set(factIds || []);
    return (detail.planning || detail.graph?.nodes || []).find(node => {
      if (node.kind && node.kind !== "planning.revision") return false;
      const basis = node.metadata?.basis_fact_ids || [];
      return basis.some(id => facts.has(id));
    }) || null;
  }

  function nextProfile(detail, index) {
    for (let i = index + 1; i < (detail.steps || []).length; i += 1) {
      const candidate = detail.steps[i];
      if (candidate.metadata?.adaptive_profile) return profile(candidate);
    }
    const rounds = (detail.graph?.nodes || []).filter(node => node.kind === "council.round" && node.metadata?.target_profile);
    const latest = rounds.at(-1)?.metadata?.target_profile || {};
    return {complexity:Number(latest.complexity || 0), unknowns:latest.unknowns || [], hypotheses:latest.hypotheses || []};
  }

  function causalRows(detail) {
    const nodes = nodeMap(detail);
    return (detail.steps || []).map((step, index) => {
      const evidence = (detail.evidence || []).find(item => item.id === step.evidence_id);
      if (!evidence) return null;
      const facts = factNodesForEvidence(detail, evidence.id, nodes);
      const factIds = facts.map(node => node.id);
      const before = profile(step);
      const after = nextProfile(detail, index);
      const revision = revisionTriggeredBy(detail, factIds);
      return {
        index:index + 1,
        tool:step.tool,
        state:step.state,
        evidence,
        facts,
        unknownsClosed:difference(before.unknowns, after.unknowns),
        unknownsOpened:difference(after.unknowns, before.unknowns),
        hypothesesAdded:difference(after.hypotheses, before.hypotheses),
        hypothesesRemoved:difference(before.hypotheses, after.hypotheses),
        complexity:after.complexity - before.complexity,
        revision,
      };
    }).filter(Boolean);
  }

  function chips(label, values) {
    if (!values.length) return "";
    return `<div class="trace-basis"><span>${esc(label)}</span>${values.map(value => `<span class="trace-fact">${esc(value)}</span>`).join("")}</div>`;
  }

  function causalCard(row) {
    const md = row.revision?.metadata || {};
    const command = `$ ${(row.evidence.argv || []).join(" ")}`;
    const next = md.tool ? `${md.tool}${md.requires_approval ? " · approval boundary" : " · governed next capability"}` : "no capability appended from these facts";
    return `<article class="trace-card" style="margin-top:7px"><div class="trace-head"><strong>E${esc(row.index)} · ${esc(row.tool)} → Evidence Delta</strong><span>${esc(row.state)} · exit ${esc(row.evidence.exit_code)}</span></div>
      <code title="${esc(command)}">${esc(command)}</code>
      ${chips("Facts produced", row.facts.map(node => node.label))}
      ${chips("Unknowns closed", row.unknownsClosed)}
      ${chips("Unknowns opened", row.unknownsOpened)}
      ${chips("Hypotheses +", row.hypothesesAdded)}
      ${chips("Hypotheses −", row.hypothesesRemoved)}
      <div class="trace-meta"><span>complexity Δ ${row.complexity > 0 ? "+" : ""}${esc(row.complexity)}</span><span>Evidence ${esc(short(row.evidence.id))}</span></div>
      <div class="trace-callout"><b>因此下一步</b><span>${esc(next)}</span></div>
      ${row.revision ? `<p>${esc(md.rationale || row.revision.label || "Evidence justified the next registered capability.")}</p><div class="trace-meta"><span>information gain: ${esc(md.expected_information_gain || "—")}</span><span>execution_authority=${md.execution_authority === false ? "false" : "—"}</span></div>` : `<p class="trace-muted">这些 Evidence 没有单独触发新的 planning.revision；Planner 保持当前边界或等待更多证据。</p>`}
    </article>`;
  }

  async function refreshExecutionDelta() {
    if (refreshing || location.pathname !== "/missions") return;
    const shell = document.querySelector("#module-page-root .decision-trace-shell");
    const runId = selectedRun();
    if (!shell || !runId || shell.querySelector(`[data-execution-delta-run="${runId}"]`)) return;
    refreshing = true;
    try {
      const response = await fetch(`/api/missions/${encodeURIComponent(runId)}`, {cache:"no-store", headers:{"Accept":"application/json"}});
      if (!response.ok) return;
      const detail = await response.json();
      if (selectedRun() !== runId || !document.contains(shell)) return;
      const rows = causalRows(detail);
      const view = document.createElement("section");
      view.dataset.executionDeltaRun = runId;
      view.className = "trace-execution-delta-view";
      view.innerHTML = `<div class="trace-title" style="margin-top:10px"><div><strong>Execution Delta · 工具级因果链</strong><span>每次实际执行 → 新 Evidence/Facts → Profile 变化 → 为什么追加或不追加下一 capability</span></div><div class="trace-legend"><span>${rows.length} executions</span><span>read only</span></div></div>${rows.map(causalCard).join("") || `<div class="trace-card" style="margin-top:7px"><span class="trace-muted">尚无已执行步骤可形成工具级 Delta。</span></div>`}`;
      const councilDelta = shell.querySelector(".trace-delta-view");
      if (councilDelta) councilDelta.insertAdjacentElement("afterend", view);
      else (shell.querySelector(".trace-profile") || shell.querySelector(".trace-title"))?.insertAdjacentElement("afterend", view);
    } finally {
      refreshing = false;
    }
  }

  const root = document.getElementById("module-page-root");
  if (root) new MutationObserver(() => queueMicrotask(refreshExecutionDelta)).observe(root, {childList:true, subtree:true});
  window.addEventListener("popstate", () => setTimeout(refreshExecutionDelta, 0));
  window.addEventListener("tonmen:runtime-event", event => {
    if (["step.completed", "step.degraded", "intelligence.created", "plan.revised", "council.round", "loop.stopped"].includes(event.detail?.type || "")) {
      document.querySelector(".trace-execution-delta-view")?.remove();
      setTimeout(refreshExecutionDelta, 120);
    }
  });
  refreshExecutionDelta();
})();
