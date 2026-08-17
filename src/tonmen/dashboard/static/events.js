(() => {
  "use strict";

  let cursor = Number(sessionStorage.getItem("tonmen.event.cursor") || "0") || 0;
  let refreshTimer = null;
  let stopped = false;
  const liveBuffers = new Map();
  const tabByRun = new Map();
  const workbenchState = {
    search: sessionStorage.getItem("tonmen.missions.search") || "",
    status: sessionStorage.getItem("tonmen.missions.status") || "all",
    split: Math.max(24, Math.min(62, Number(localStorage.getItem("tonmen.missions.historySize") || "36") || 36)),
  };

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
  const stripAnsi = value => String(value ?? "")
    .replace(/\u001b\][^\u0007]*(?:\u0007|\u001b\\)/g, "")
    .replace(/\u001b\[[0-?]*[ -\/]*[@-~]/g, "");
  const short = value => String(value || "").slice(0, 8);
  const stateName = state => ({pending:"待行", running:"运行", waiting_approval:"候旨", succeeded:"完成", skipped:"跳过", degraded:"降级", failed:"失败", denied:"拒绝"}[state] || state || "—");
  const stateTone = state => state === "succeeded" ? "ok" : state === "running" || state === "waiting_approval" ? "warn" : state === "failed" || state === "denied" ? "bad" : "blue";

  function selectedRun() {
    const explicit = new URLSearchParams(location.search).get("run");
    if (explicit) return explicit;
    return document.querySelector(".module-table tr.selected[data-select-run]")?.dataset.selectRun || null;
  }

  function eventLine(event) {
    const data = event.data || {};
    const time = new Date(event.timestamp).toLocaleTimeString();
    if (event.type === "tool.output") {
      const stream = data.stream || "stdout";
      const tool = data.tool || "tool";
      return `[${time}] [${tool}] [${stream}] ${stripAnsi(String(data.chunk || "").replace(/\n$/, ""))}`;
    }
    const step = data.step_id ? ` step=${short(data.step_id)}` : "";
    const tool = data.tool ? ` tool=${data.tool}` : "";
    const reason = data.reason ? ` reason=${data.reason}` : "";
    const action = data.action ? ` action=${data.action}` : "";
    return `[${time}] ${event.type}${step}${tool}${reason}${action}`;
  }

  function bufferFor(missionId) {
    if (!missionId) return null;
    if (!liveBuffers.has(missionId)) liveBuffers.set(missionId, []);
    return liveBuffers.get(missionId);
  }

  function appendEvent(event) {
    window.dispatchEvent(new CustomEvent("tonmen:runtime-event", { detail: event }));
    const missionId = event.data?.mission_id;
    const buffer = bufferFor(missionId);
    if (buffer) {
      buffer.push(eventLine(event));
      if (buffer.length > 1600) buffer.splice(0, buffer.length - 1200);
    }
    if (location.pathname !== "/missions" || !missionId || selectedRun() !== missionId) return;
    const output = document.getElementById("mission-live-output");
    if (!output) return;
    output.textContent = buffer.join("\n") || "等待当前任务的实时执行事件…";
    output.scrollTop = output.scrollHeight;
  }

  function requestRefresh(event) {
    if (event.type === "tool.output") return;
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => {
      if (document.hidden) return;
      if (location.pathname === "/") document.getElementById("refresh-btn")?.click();
      else document.querySelector("[data-module-refresh]")?.click();
    }, 120);
  }

  async function poll() {
    while (!stopped) {
      try {
        const response = await fetch(`/api/events?cursor=${cursor}&timeout=20&limit=200`, {
          cache: "no-store",
          headers: {"Accept":"application/json"}
        });
        if (!response.ok) throw new Error(`event stream ${response.status}`);
        const payload = await response.json();
        for (const event of payload.events || []) {
          cursor = Math.max(cursor, Number(event.cursor) || cursor);
          appendEvent(event);
          requestRefresh(event);
        }
        cursor = Math.max(cursor, Number(payload.cursor) || cursor);
        sessionStorage.setItem("tonmen.event.cursor", String(cursor));
      } catch (_) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
  }

  function encodeCopy(value) {
    return encodeURIComponent(String(value ?? ""));
  }

  function copyButton(label, value) {
    return `<button class="ghost mission-copy" type="button" data-copy-text="${esc(encodeCopy(value))}">⧉ ${esc(label)}</button>`;
  }

  function filterMissionRows(historyCard) {
    const query = workbenchState.search.trim().toLowerCase();
    const status = workbenchState.status;
    const label = {running:"运行", waiting_approval:"候旨", failed:"失败", denied:"拒绝", succeeded:"完成"}[status] || "";
    let visible = 0;
    historyCard.querySelectorAll("tbody tr[data-select-run]").forEach(row => {
      const text = row.textContent.toLowerCase();
      const stateText = row.querySelector(".module-badge")?.textContent || "";
      const ok = (!query || text.includes(query)) && (status === "all" || stateText.includes(label));
      row.hidden = !ok;
      if (ok) visible += 1;
    });
    const count = historyCard.querySelector("[data-visible-runs]");
    if (count) count.textContent = `${visible} visible`;
  }

  function installHistoryTools(historyCard) {
    const head = historyCard.querySelector(".module-card-head");
    if (!head || historyCard.querySelector(".mission-history-tools")) return;
    const tools = document.createElement("div");
    tools.className = "mission-history-tools";
    tools.innerHTML = `
      <div class="mission-search-wrap"><span>⌕</span><input id="mission-history-filter" type="search" placeholder="搜索 Run / Target…" value="${esc(workbenchState.search)}"></div>
      <select id="mission-state-filter" aria-label="Filter mission state">
        <option value="all">全部状态</option><option value="running">运行</option><option value="waiting_approval">候旨</option><option value="failed">失败</option><option value="denied">拒绝</option><option value="succeeded">完成</option>
      </select>
      <small data-visible-runs></small>`;
    head.insertAdjacentElement("afterend", tools);
    const search = tools.querySelector("#mission-history-filter");
    const select = tools.querySelector("#mission-state-filter");
    select.value = workbenchState.status;
    search.addEventListener("input", () => {
      workbenchState.search = search.value;
      sessionStorage.setItem("tonmen.missions.search", workbenchState.search);
      filterMissionRows(historyCard);
    });
    select.addEventListener("change", () => {
      workbenchState.status = select.value;
      sessionStorage.setItem("tonmen.missions.status", workbenchState.status);
      filterMissionRows(historyCard);
    });
    filterMissionRows(historyCard);
  }

  function installSplitter(grid, historyCard, detailCard) {
    if (grid.querySelector(".mission-splitter")) return;
    grid.style.setProperty("--mission-history-size", `${workbenchState.split}%`);
    const splitter = document.createElement("div");
    splitter.className = "mission-splitter";
    splitter.setAttribute("role", "separator");
    splitter.setAttribute("aria-orientation", "horizontal");
    splitter.title = "拖动调整任务历史与详情高度";
    grid.insertBefore(splitter, detailCard);
    splitter.addEventListener("pointerdown", event => {
      if (matchMedia("(max-width: 900px)").matches) return;
      event.preventDefault();
      splitter.setPointerCapture?.(event.pointerId);
      const rect = grid.getBoundingClientRect();
      const move = moveEvent => {
        const next = Math.max(24, Math.min(62, ((moveEvent.clientY - rect.top) / rect.height) * 100));
        workbenchState.split = next;
        grid.style.setProperty("--mission-history-size", `${next}%`);
      };
      const done = () => {
        localStorage.setItem("tonmen.missions.historySize", String(workbenchState.split));
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", done);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", done, {once:true});
    });
    historyCard.classList.add("mission-master-card");
    detailCard.classList.add("mission-detail-card");
  }

  function evidenceTerminal(item, stream) {
    const value = stripAnsi(item?.[stream] || "");
    return `<section class="mission-output-block"><div><strong>${esc(item.tool)} · ${esc(short(item.id))}</strong><span>exit ${esc(item.exit_code)}</span>${copyButton(`复制 ${stream}`, value)}</div><pre class="terminal mission-output ${stream}">${esc(value || "(empty)")}</pre></section>`;
  }

  function overviewPanel(detail) {
    const failed = (detail.steps || []).filter(step => step.state === "failed" || step.state === "denied").length;
    const degraded = (detail.steps || []).filter(step => step.state === "degraded").length;
    const waiting = (detail.steps || []).filter(step => step.state === "waiting_approval").length;
    return `<div class="mission-summary-grid">
      <div><span>Target</span><strong>${esc(detail.target)}</strong></div>
      <div><span>State</span><strong>${esc(stateName(detail.state))}</strong></div>
      <div><span>Steps</span><strong>${detail.steps?.length || 0}</strong></div>
      <div><span>Evidence</span><strong>${detail.evidence?.length || 0}</strong></div>
      <div><span>Failed</span><strong>${failed}</strong></div>
      <div><span>Degraded / Waiting</span><strong>${degraded} / ${waiting}</strong></div>
    </div>
    <div class="mission-context-links">
      <a href="/intelligence?run=${encodeURIComponent(detail.id)}">查看天鑑 Intelligence</a>
      <a href="/reasoner?run=${encodeURIComponent(detail.id)}">查看天策 Reasoner</a>
      <a href="/chronicle?run=${encodeURIComponent(detail.id)}">查看天冊 Chronicle</a>
      ${detail.state === "waiting_approval" ? `<a class="attention" href="/approval?run=${encodeURIComponent(detail.id)}">前往审批 Approval</a>` : ""}
    </div>`;
  }

  function stepsPanel(detail) {
    return `<div class="mission-step-list">${(detail.steps || []).map((step, index) => `<article class="mission-step-row">
      <span class="num">${String(index + 1).padStart(2, "0")}</span>
      <div><strong>${esc(step.tool)}</strong><code>${esc(step.target)}</code><small class="${step.error ? "err" : ""}">${esc(step.error || step.rationale || "")}</small></div>
      <div class="mission-step-meta"><span class="module-badge ${stateTone(step.state)}">${esc(stateName(step.state))}</span><small>exit ${esc(step.metadata?.exit_code ?? "—")}</small></div>
    </article>`).join("") || `<div class="module-empty">暂无步骤。</div>`}</div>`;
  }

  function evidencePanel(detail) {
    if (!detail.evidence?.length) return `<div class="module-empty"><b>暂无 Evidence</b>执行产生原始证据后会显示在这里。</div>`;
    return detail.evidence.slice().reverse().map(item => {
      const command = (item.argv || []).join(" ");
      return `<article class="mission-evidence-row"><div class="mission-evidence-head"><div><strong>${esc(item.tool)} · ${esc(short(item.id))}</strong><small>${esc(item.started_at || "")} → ${esc(item.finished_at || "")}</small></div><span class="module-badge ${item.exit_code === 0 ? "ok" : "bad"}">exit ${esc(item.exit_code)}</span></div><code>$ ${esc(command)}</code><div class="mission-copy-row">${copyButton("复制命令", command)}${copyButton("复制原始 stdout", item.stdout || "")}${copyButton("复制原始 stderr", item.stderr || "")}</div></article>`;
    }).join("");
  }

  function reasoningPanel(detail) {
    if (!detail.reasoning?.length) return `<div class="module-empty"><b>暂无 Reasoning</b>天策做出决策后会显示依据与下一步。</div>`;
    return detail.reasoning.slice().reverse().map(node => `<article class="mission-reason-row"><div><strong>${esc(node.metadata?.action || node.kind)}</strong><span>${esc(node.label)}</span></div><small>basis: ${esc((node.metadata?.basis_fact_ids || []).map(short).join(", ") || "—")} · next: ${esc(short(node.metadata?.next_step_id) || "—")} · human: ${node.metadata?.requires_human ? "yes" : "no"}</small></article>`).join("");
  }

  function livePanel(detail) {
    const lines = liveBuffers.get(detail.id) || [];
    return `<pre id="mission-live-output" class="terminal mission-live-output">${esc(lines.join("\n") || "等待当前任务的实时执行事件…")}</pre>`;
  }

  function outputPanel(detail, stream) {
    if (!detail.evidence?.length) return `<div class="module-empty">暂无 ${esc(stream)}。</div>`;
    return detail.evidence.slice().reverse().map(item => evidenceTerminal(item, stream)).join("");
  }

  function renderDetailTabs(detailCard, detail) {
    const body = detailCard.querySelector(".module-card-body");
    if (!body) return;
    if (!tabByRun.has(detail.id)) tabByRun.set(detail.id, detail.state === "running" ? "live" : detail.state === "failed" ? "stderr" : "steps");
    const active = tabByRun.get(detail.id);
    const tabs = [
      ["overview", "概览"], ["steps", "Steps"], ["live", "Live"], ["stdout", "stdout"], ["stderr", "stderr"], ["evidence", "Evidence"], ["reasoning", "Reasoning"]
    ];
    const panels = {
      overview: overviewPanel(detail), steps: stepsPanel(detail), live: livePanel(detail),
      stdout: outputPanel(detail, "stdout"), stderr: outputPanel(detail, "stderr"),
      evidence: evidencePanel(detail), reasoning: reasoningPanel(detail)
    };
    body.innerHTML = `<div class="mission-detail-summary"><div><strong>${esc(detail.target)}</strong><small>Run ${esc(detail.id)} · Plan ${esc(detail.plan_id)}</small></div><span class="module-badge ${stateTone(detail.state)}">${esc(stateName(detail.state))}</span></div>
      <div class="mission-detail-tabs" role="tablist">${tabs.map(([key, label]) => `<button type="button" role="tab" data-mission-tab="${key}" class="${active === key ? "active" : ""}">${label}</button>`).join("")}</div>
      <div class="mission-tab-content">${tabs.map(([key]) => `<section data-tab-panel="${key}" class="mission-tab-panel ${active === key ? "active" : ""}">${panels[key]}</section>`).join("")}</div>`;

    body.querySelectorAll("[data-mission-tab]").forEach(button => button.addEventListener("click", () => {
      const key = button.dataset.missionTab;
      tabByRun.set(detail.id, key);
      body.querySelectorAll("[data-mission-tab]").forEach(item => item.classList.toggle("active", item === button));
      body.querySelectorAll("[data-tab-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.tabPanel === key));
    }));
    body.querySelectorAll("[data-copy-text]").forEach(button => button.addEventListener("click", async () => {
      const text = decodeURIComponent(button.dataset.copyText || "");
      try {
        await navigator.clipboard.writeText(text);
        const old = button.textContent; button.textContent = "✓ 已复制";
        setTimeout(() => { button.textContent = old; }, 1200);
      } catch (_) {
        window.prompt("复制内容", text);
      }
    }));
  }

  async function loadDetailIntoWorkbench(detailCard, runId) {
    try {
      const response = await fetch(`/api/missions/${encodeURIComponent(runId)}`, {cache:"no-store", headers:{"Accept":"application/json"}});
      if (!response.ok) return;
      const detail = await response.json();
      if (!document.contains(detailCard) || selectedRun() !== runId) return;
      renderDetailTabs(detailCard, detail);
    } catch (_) {}
  }

  function enhanceMissions() {
    if (location.pathname !== "/missions") return;
    const root = document.getElementById("module-page-root");
    const grid = root?.querySelector(".module-grid.two");
    if (!grid || grid.classList.contains("mission-workbench")) return;
    const cards = Array.from(grid.children).filter(item => item.classList?.contains("module-card"));
    const historyCard = cards[0], detailCard = cards[1];
    if (!historyCard || !detailCard || !historyCard.querySelector(".module-table")) return;
    grid.classList.add("mission-workbench");
    installHistoryTools(historyCard);
    installSplitter(grid, historyCard, detailCard);
    let runId = selectedRun();
    if (runId && !new URLSearchParams(location.search).get("run")) {
      const params = new URLSearchParams(location.search); params.set("run", runId);
      history.replaceState({}, "", `${location.pathname}?${params.toString()}`);
    }
    runId = selectedRun();
    if (runId) loadDetailIntoWorkbench(detailCard, runId);
  }

  function bindWorkbenchKeys() {
    window.addEventListener("keydown", event => {
      if (location.pathname !== "/missions") return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.getElementById("mission-history-filter")?.focus();
      }
      if (event.altKey && /^[1-7]$/.test(event.key)) {
        const tabs = Array.from(document.querySelectorAll("[data-mission-tab]"));
        const target = tabs[Number(event.key) - 1];
        if (target) { event.preventDefault(); target.click(); }
      }
    });
  }

  function observeMissions() {
    const root = document.getElementById("module-page-root");
    if (!root) return;
    const observer = new MutationObserver(() => queueMicrotask(enhanceMissions));
    observer.observe(root, {childList:true, subtree:true});
    enhanceMissions();
  }

  window.addEventListener("beforeunload", () => { stopped = true; });
  window.addEventListener("popstate", () => setTimeout(enhanceMissions, 0));
  bindWorkbenchKeys();
  observeMissions();
  poll();
})();

(() => {
  "use strict";

  let cache = {at: 0, tools: new Map()};
  let enhancing = false;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));

  async function readiness(force = false) {
    if (!force && Date.now() - cache.at < 1500 && cache.tools.size) return cache.tools;
    const response = await fetch("/api/tools", {cache:"no-store", headers:{"Accept":"application/json"}});
    if (!response.ok) return cache.tools;
    const payload = await response.json();
    cache = {at: Date.now(), tools: new Map((payload.tools || []).map(tool => [tool.name, tool]))};
    return cache.tools;
  }

  function repairCommand(tool) {
    return tool?.name === "nuclei" && tool?.doctor?.code === "missing_templates" ? "nuclei -ut" : "";
  }

  async function copyText(text, button) {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      const before = button.textContent;
      button.textContent = "✓ 已复制";
      setTimeout(() => { button.textContent = before; }, 1200);
    } catch (_) {
      window.prompt("复制修复命令", text);
    }
  }

  function updateLiveLabel() {
    const label = document.querySelector("#module-page-root .module-live span");
    if (label && !label.dataset.eventLabel) {
      const clock = label.querySelector("b")?.outerHTML || "";
      label.innerHTML = `EVENT STREAM · 2.5s fallback · ${clock}`;
      label.dataset.eventLabel = "1";
    }
  }

  function decorateToolCards(tools) {
    if (location.pathname !== "/tools") return;
    document.querySelectorAll("#module-page-root .tool-card").forEach(card => {
      const name = card.querySelector("h3")?.textContent?.trim();
      const tool = tools.get(name);
      if (!tool || tool.available || card.querySelector(".tool-readiness-fix")) return;
      const block = document.createElement("div");
      block.className = "tool-readiness-fix";
      const command = repairCommand(tool);
      block.innerHTML = `<strong>${esc((tool.doctor?.code || "blocked").replaceAll("_", " ").toUpperCase())}</strong><span>${esc(tool.doctor?.detail || "Tool environment is not ready.")}</span>${tool.doctor?.remediation ? `<small>${esc(tool.doctor.remediation)}</small>` : ""}${command ? `<button type="button" class="ghost small" data-readiness-copy="${esc(command)}">⧉ 复制修复命令</button>` : ""}`;
      card.appendChild(block);
      block.querySelector("[data-readiness-copy]")?.addEventListener("click", event => copyText(event.currentTarget.dataset.readinessCopy, event.currentTarget));
    });
  }

  function decorateApproval(tools) {
    if (location.pathname !== "/approval") return;
    document.querySelectorAll("#module-page-root .approval-workitem").forEach(item => {
      const title = item.querySelector("h3")?.textContent || "";
      const name = title.split("·", 1)[0].trim();
      const tool = tools.get(name);
      if (!tool || tool.available || item.querySelector(".approval-preflight-block")) return;
      const button = item.querySelector("[data-approve-run]");
      if (button) {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
        button.textContent = "环境未就绪 · 无法批准执行";
      }
      const command = repairCommand(tool);
      const block = document.createElement("div");
      block.className = "approval-preflight-block";
      block.innerHTML = `<strong>PRE-FLIGHT BLOCKED · ${esc((tool.doctor?.code || "tool_not_ready").replaceAll("_", " "))}</strong><span>${esc(tool.doctor?.detail || "Tool environment is not ready.")}</span>${tool.doctor?.remediation ? `<small>${esc(tool.doctor.remediation)}</small>` : ""}${command ? `<button type="button" class="ghost small" data-readiness-copy="${esc(command)}">⧉ 复制 ${esc(command)}</button>` : ""}`;
      item.querySelector(".approval-actions")?.before(block);
      block.querySelector("[data-readiness-copy]")?.addEventListener("click", event => copyText(event.currentTarget.dataset.readinessCopy, event.currentTarget));
    });
  }

  async function enhance() {
    if (enhancing || !["/tools", "/approval", "/settings", "/missions", "/guard", "/loop", "/chronicle", "/intelligence", "/reasoner", "/scope"].includes(location.pathname)) return;
    enhancing = true;
    try {
      updateLiveLabel();
      if (location.pathname === "/tools" || location.pathname === "/approval") {
        const tools = await readiness();
        decorateToolCards(tools);
        decorateApproval(tools);
      }
    } catch (_) {
      // Readiness decoration is supplemental; core pages remain usable if it cannot load.
    } finally {
      enhancing = false;
    }
  }

  const root = document.getElementById("module-page-root");
  if (root) {
    new MutationObserver(() => queueMicrotask(enhance)).observe(root, {childList:true, subtree:true});
  }
  window.addEventListener("popstate", () => setTimeout(() => enhance(), 0));
  window.addEventListener("tonmen:runtime-event", event => {
    if (event.detail?.type === "tool.preflight_blocked") cache.at = 0;
  });
  enhance();
})();
