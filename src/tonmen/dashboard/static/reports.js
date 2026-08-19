(() => {
  "use strict";

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
  const short = value => String(value || "").slice(0, 8);
  let intelligenceBusy = false;
  let intelligenceLastAt = 0;

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

  function toneFor(status) {
    if (["confirmed", "supported", "same_backend", "matched"].includes(status)) return "ok";
    if (["contradicted", "not_confirmed", "different_backend", "different_resolved_backend"].includes(status)) return "bad";
    if (["observed", "unverified", "matched_only", "uncompared"].includes(status)) return "warn";
    return "blue";
  }

  function badge(label, status) {
    return `<span class="module-badge ${toneFor(status)}">${esc(label)}: ${esc(status || "unknown")}</span>`;
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
    const verify = item.verification || {};
    const backend = item.backend_correlation || {};
    return `<details class="report-payload" ${index === 0 ? "open" : ""}>
      <summary><strong>${esc(item.template_id || item.name || `Payload ${index + 1}`)}</strong><span>${esc(item.severity || "unknown")}</span><code>${esc(item.matched_at || "")}</code></summary>
      <div class="fact-meta" style="padding:9px 0">${badge("Template", verify.template_status)}${badge("Evidence", verify.evidence_status)}${badge("Attribution", verify.attribution_status)}${badge("Backend", backend.status)}</div>
      <div class="report-kv"><span>Template</span><code>${esc(item.template_path || item.template || "—")}</code><span>Host / IP</span><code>${esc(item.host || "—")} / ${esc(item.ip || "—")}</code><span>Observed Server</span><code>${esc(verify.observed_server || "—")}</code><span>Nmap scanned</span><code>${esc((backend.nmap_scanned_addresses || []).join(", ") || "—")}</code><span>Other resolved/not scanned</span><code>${esc((backend.resolved_addresses_not_scanned || []).join(", ") || "—")}</code></div>
      <p style="color:#93aab5;font-size:10px">${esc(backend.note || "")} ${esc(backend.affected_scope || "")}</p>
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
      const data = md.data || {};
      const verify = data.verification || {};
      return `<article class="report-finding"><div><strong>${esc(item.label)}</strong><span class="module-badge ${["critical","high"].includes(md.severity) ? "bad" : md.severity === "medium" ? "warn" : "blue"}">${esc(md.severity || "unknown")}</span></div><small>Evidence ${esc(short(md.evidence_id))} · confidence ${esc(md.confidence ?? "—")} · affected IP ${esc(verify.observed_ip || "—")}</small><div class="fact-meta" style="margin-top:7px">${badge("Template", verify.template_status)}${badge("Evidence", verify.evidence_status)}${badge("Attribution", verify.attribution_status)}</div><code>${esc((verify.attribution_reasons || []).join(" · ") || verify.note || "")}</code></article>`;
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
      <div><span>Target</span><strong>${esc(mission.target)}</strong></div><div><span>State</span><strong>${esc(mission.state)}</strong></div><div><span>Report</span><strong>${esc(report.report_type)}</strong></div><div><span>Findings</span><strong>${summary.findings || 0}</strong></div><div><span>Evidence confirmed</span><strong>${summary.evidence_confirmed || 0}</strong></div><div><span>Attribution supported</span><strong>${summary.attribution_supported || 0}</strong></div><div><span>Attribution contradicted</span><strong>${summary.attribution_contradicted || 0}</strong></div><div><span>Backend divergences</span><strong>${summary.backend_divergences || 0}</strong></div><div><span>Rounds</span><strong>${summary.assessment_rounds || 0}</strong></div><div><span>Subagent reviews</span><strong>${summary.subagent_reviews || 0}</strong></div>
    </section>
    <section class="report-section"><h3>Finding Verification</h3><p>Template Matched、Evidence Confirmed、CVE/Root-cause Attribution 是三个独立结论；多 IP 域名不会自动视为同一后端。</p></section>
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
        const summaryText = `${report.mission?.target || ""} · ${report.mission?.state || ""} · ${report.summary?.findings || 0} findings · ${report.summary?.evidence_confirmed || 0} evidence-confirmed · ${report.summary?.attribution_supported || 0} attribution-supported · ${report.summary?.backend_divergences || 0} backend divergences`;
        try { await navigator.clipboard.writeText(summaryText); toast("报告摘要已复制"); }
        catch (_) { window.prompt("复制报告摘要", summaryText); }
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

  async function renderIntelligenceVerification() {
    if (location.pathname !== "/intelligence" || intelligenceBusy || Date.now() - intelligenceLastAt < 1200) return;
    const root = document.getElementById("module-page-root");
    const head = root?.querySelector(".module-page-head");
    if (!root || !head) return;
    intelligenceBusy = true;
    intelligenceLastAt = Date.now();
    try {
      const listResponse = await fetch("/api/missions", {cache:"no-store"});
      const listPayload = await listResponse.json();
      const runs = (listPayload.missions || []).slice(0, 20);
      const details = await Promise.all(runs.map(async run => {
        try {
          const response = await fetch(`/api/missions/${encodeURIComponent(run.id)}`, {cache:"no-store"});
          return response.ok ? await response.json() : null;
        } catch (_) { return null; }
      }));
      const findings = details.filter(Boolean).flatMap(run => (run.intelligence || [])
        .filter(node => node.kind === "intelligence.finding")
        .map(node => ({...node, run_id:run.id, run_target:run.target})));
      let panel = document.getElementById("finding-verification-matrix");
      if (!panel) {
        panel = document.createElement("section");
        panel.id = "finding-verification-matrix";
        panel.className = "module-card";
        head.insertAdjacentElement("afterend", panel);
      }
      const rows = findings.slice().reverse().map(node => {
        const md = node.metadata || {};
        const verify = md.data?.verification || {};
        return `<article class="fact-item"><h3>${esc(node.label)} <span class="module-badge ${["critical","high"].includes(md.severity) ? "bad" : "warn"}">${esc(md.severity || "unknown")}</span></h3><p>${esc(node.run_target)} · affected IP ${esc(verify.observed_ip || "—")} · Server ${esc(verify.observed_server || "—")}</p><div class="fact-meta">${badge("Template", verify.template_status)}${badge("Evidence", verify.evidence_status)}${badge("Attribution", verify.attribution_status)}<span class="module-badge">confidence ${esc(md.confidence ?? "—")}</span><button class="ghost small" data-open-run="${esc(node.run_id)}">Run ${esc(short(node.run_id))}</button></div></article>`;
      }).join("");
      panel.innerHTML = `<div class="module-card-head"><h2>Finding Verification Matrix</h2><small>Template ≠ Evidence ≠ Attribution</small></div><div class="module-card-body"><div class="fact-list">${rows || `<div class="module-empty"><b>暂无需要验证的 Finding</b>Nuclei 结构化命中后会在这里分层显示可信度。</div>`}</div></div>`;
      panel.querySelectorAll("[data-open-run]").forEach(button => button.addEventListener("click", () => {
        history.pushState({}, "", `/missions?run=${encodeURIComponent(button.dataset.openRun)}`);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }));
    } catch (_) {
      // Existing Intelligence workspace remains usable if enrichment fails.
    } finally {
      intelligenceBusy = false;
    }
  }

  window.addEventListener("tonmen:runtime-event", event => {
    const runtime = event.detail || {};
    if (runtime.type === "report.ready") {
      const runId = runtime.data?.mission_id;
      if (runId) {
        const key = `tonmen.report.shown.${runId}`;
        if (!sessionStorage.getItem(key)) {
          sessionStorage.setItem(key, "1");
          openReport(runId, {auto:true});
        }
      }
    }
    if (runtime.type === "intelligence.created" || runtime.type === "report.ready") {
      setTimeout(renderIntelligenceVerification, 150);
    }
  });

  const root = document.getElementById("module-page-root");
  if (root) new MutationObserver(() => {
    queueMicrotask(installReportButton);
    if (location.pathname === "/intelligence") setTimeout(renderIntelligenceVerification, 80);
  }).observe(root, {childList:true, subtree:true});
  window.addEventListener("popstate", () => {
    setTimeout(installReportButton, 0);
    setTimeout(renderIntelligenceVerification, 100);
  });
  setTimeout(installReportButton, 0);
  setTimeout(renderIntelligenceVerification, 100);
})();
