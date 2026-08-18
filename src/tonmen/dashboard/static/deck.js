(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);

  const moduleRoutes = [
    ["儀表總覽", "/"],
    ["任務", "/missions"],
    ["天域", "/scope"],
    ["天律", "/guard"],
    ["天工", "/tools"],
    ["天鑑", "/intelligence"],
    ["天策", "/reasoner"],
    ["天衡", "/loop"],
    ["天冊", "/chronicle"],
    ["審批", "/approval"],
    ["設定", "/settings"],
  ];

  function routeForNav(item) {
    const text = item?.textContent?.trim() || "";
    return moduleRoutes.find(([label]) => text.startsWith(label))?.[1] || null;
  }

  document.addEventListener("click", (event) => {
    const item = event.target.closest?.(".nav-item");
    if (!item) return;
    const route = routeForNav(item);
    if (!route) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const current = location.pathname.replace(/\/+$/, "") || "/";
    if (current === route) return;
    location.assign(route);
  }, true);

  function clickProxy(selector, unavailableMessage) {
    const source = $(selector);
    if (!source || source.disabled) {
      const toast = $("#toast");
      if (toast) {
        toast.textContent = unavailableMessage;
        toast.className = "toast show error";
        setTimeout(() => { toast.className = "toast"; }, 2600);
      }
      return;
    }
    source.click();
  }

  function setDisabled(selector, disabled) {
    const button = $(selector);
    if (button && button.disabled !== disabled) button.disabled = disabled;
  }

  function syncDeck() {
    const newMission = $("#new-mission-btn") || $("#empty-new-mission-btn");
    const resume = $("#resume-btn");
    const approve = $("#approve-btn");
    const evidence = $("#evidence-btn");
    const retry = $("#retry-btn");

    setDisabled("#deck-new-mission", !newMission || newMission.disabled);
    setDisabled("#deck-resume", !resume || resume.disabled);
    setDisabled("#deck-approve", !approve || approve.disabled);
    setDisabled("#deck-evidence", !evidence || evidence.disabled);
    setDisabled("#deck-retry", !retry || retry.disabled);

    const target = $("#mission-target")?.textContent?.trim();
    const missionState = $("#mission-state")?.textContent?.trim();
    const current = $("#deck-current");
    if (current) {
      const text = target && target !== "—"
        ? `${target} · ${missionState && missionState !== "—" ? missionState : "unknown"}`
        : "尚無任務";
      if (current.textContent !== text) current.textContent = text;
    }
  }

  $("#deck-new-mission")?.addEventListener("click", () => clickProxy("#new-mission-btn, #empty-new-mission-btn", "目前無法建立任務。"));
  $("#deck-refresh")?.addEventListener("click", () => clickProxy("#refresh-btn", "刷新控制目前不可用。"));
  $("#deck-resume")?.addEventListener("click", () => clickProxy("#resume-btn", "目前任務不在可續行狀態。"));
  $("#deck-approve")?.addEventListener("click", () => clickProxy("#approve-btn", "目前沒有等待人工批准的步驟。"));
  $("#deck-evidence")?.addEventListener("click", () => clickProxy("#evidence-btn", "目前任務沒有可查看的證據。"));
  $("#deck-retry")?.addEventListener("click", () => clickProxy("#retry-btn", "目前任務不是可重跑的失敗狀態。"));

  $("#deck-scope-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const deckInput = $("#deck-scope-input");
    const sourceInput = $("#scope-input");
    const sourceForm = $("#scope-form");
    const value = deckInput?.value?.trim();
    if (!value || !sourceInput || !sourceForm) return;
    sourceInput.value = value;
    sourceForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    deckInput.value = "";
  });

  const observer = new MutationObserver(syncDeck);
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["disabled", "class"]
  });

  document.addEventListener("visibilitychange", syncDeck);
  window.addEventListener("focus", syncDeck);
  syncDeck();
})();

(() => {
  "use strict";

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const stateName = value => ({pending:"待行",running:"运行",waiting_approval:"候旨",succeeded:"完成",degraded:"降级",skipped:"跳过",failed:"失败",denied:"拒绝"}[value] || value || "—");
  const short = value => String(value || "").slice(0, 8);

  async function api(url, options = {}) {
    const opts = {...options, headers:{...(options.headers || {})}};
    if (opts.body && typeof opts.body !== "string") {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    if ((opts.method || "GET") !== "GET") opts.headers["X-TONMEN-CSRF"] = csrf;
    const response = await fetch(url, opts);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data;
  }

  function installOperatorNav() {
    const sidebar = document.querySelector(".sidebar");
    const legacy = sidebar?.querySelector(":scope > .nav");
    if (!sidebar || !legacy || sidebar.querySelector(".operator-nav")) return;
    const nav = document.createElement("nav");
    nav.className = "operator-nav";
    nav.setAttribute("aria-label", "Operator workflow navigation");
    const links = [
      ["/", "▶", "开始 / 控制台", "创建计划与任务"],
      ["/missions", "⌁", "实时执行", "工具、参数、stdout / stderr"],
      ["/intelligence", "◉", "数据 / 证据", "Facts、Findings、Evidence"],
      ["/approval", "♙", "审批", "所有候旨步骤集中处理"],
      ["/chronicle", "▤", "记录 / 删除", "历史、报告、清理记录"],
      ["/scope", "◎", "授权范围", "目标 Scope 与边界"],
    ];
    nav.innerHTML = links.map(([href, icon, label, sub]) => `<a href="${href}" class="${path === href ? "active" : ""}"><span class="op-icon">${icon}</span><span><strong>${label}</strong><small>${sub}</small></span></a>`).join("") + `
      <button type="button" data-operator-plan><span class="op-icon">✺</span><span><strong>生成测试计划</strong><small>只预览，不执行</small></span></button>
      <details><summary>高级模块 ▾</summary><div class="advanced-links">
        <a href="/tools">天工 / Tools</a><a href="/guard">天律 / Guard</a><a href="/reasoner">天策 / Reasoner</a><a href="/loop">天衡 / Loop</a><a href="/settings">设置 / Doctor</a>
      </div></details>`;
    legacy.before(nav);
    nav.querySelector("[data-operator-plan]")?.addEventListener("click", () => openPlanDialog());
  }

  const plannedSteps = [
    {tool:"nmap", title:"网络入口确认", operation:"TCP 80/443 可达性，不做版本探测", params:"ports=80,443 · service_detection=false", risk:"L1 · 自动"},
    {tool:"httpx", title:"Web 元数据", operation:"HTTP 状态、标题与技术栈识别", params:"redirects=false · timeout=10s", risk:"L1 · 自动"},
    {tool:"crawler", title:"同域爬虫", operation:"发现站内页面与端点；不提交表单、不跨主机", params:"max_pages=25 · depth=2 · timeout=10s", risk:"L1 · 自动"},
    {tool:"nuclei", title:"漏洞验证", operation:"基于模板的受控验证，仅在已有 Web Evidence 后进入", params:"severity=medium,high,critical · rate=10", risk:"L3 · 人工审批", approval:true},
  ];

  function ensurePlanDialog() {
    let dialog = document.getElementById("operator-plan-dialog");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "operator-plan-dialog";
    dialog.className = "operator-plan-dialog";
    dialog.innerHTML = `<div class="operator-plan-shell">
      <div class="operator-plan-head"><div><h2>测试 / 攻击面评估计划</h2><p>先看会做什么，再决定是否启动。这里不会执行任何工具。</p></div><button class="ghost" type="button" data-plan-close>×</button></div>
      <div class="operator-plan-target"><input data-plan-target placeholder="已授权 Target，例如 https://app.example.test"><button class="primary" type="button" data-plan-build>生成计划</button></div>
      <div data-plan-result class="operator-plan-list"><div class="operator-empty">输入 Target 后生成计划预览。</div></div>
      <div class="operator-capability-strip">
        <div><strong>Web 渗透 / Recon · 已接入</strong><span>Nmap + HTTPx + Crawler + Nuclei，低风险自动运行到审批边界。</span></div>
        <div><strong>逆向 / Binary · 下一阶段</strong><span>先补 Artifact Intake、ELF/PE 静态解析与证据模型，再接反汇编分析。</span></div>
        <div><strong>会话 / 劫持风险 · 下一阶段</strong><span>做 Cookie、CORS、TLS、DNS/Redirect 风险检测与靶场验证，不自动窃取或接管会话。</span></div>
        <div><strong>高风险 Exploit · 审批隔离</strong><span>候选动作只能由 Reasoner 提议；Scope、Policy 与人工批准继续掌握执行权。</span></div>
      </div>
      <div class="operator-plan-actions"><a class="ghost" href="/scope">先配置授权范围</a><button class="ghost" type="button" data-plan-close>关闭</button><button class="primary" type="button" data-plan-start disabled>使用此 Target 建立任务</button></div>
    </div>`;
    document.body.appendChild(dialog);
    dialog.querySelectorAll("[data-plan-close]").forEach(button => button.addEventListener("click", () => dialog.close()));
    dialog.querySelector("[data-plan-build]")?.addEventListener("click", () => renderPlan(dialog));
    dialog.querySelector("[data-plan-target]")?.addEventListener("keydown", event => {
      if (event.key === "Enter") { event.preventDefault(); renderPlan(dialog); }
    });
    dialog.querySelector("[data-plan-start]")?.addEventListener("click", () => {
      const target = dialog.querySelector("[data-plan-target]")?.value?.trim();
      if (!target) return;
      dialog.close();
      const missionInput = document.getElementById("mission-input");
      if (missionInput) missionInput.value = target;
      document.getElementById("mission-dialog")?.showModal();
    });
    return dialog;
  }

  async function renderPlan(dialog) {
    const target = dialog.querySelector("[data-plan-target]")?.value?.trim();
    const result = dialog.querySelector("[data-plan-result]");
    const start = dialog.querySelector("[data-plan-start]");
    if (!target || !result || !start) return;
    result.innerHTML = `<div class="operator-empty">正在读取 Tool Registry…</div>`;
    try {
      const tools = (await api("/api/tools")).tools || [];
      const readiness = new Map(tools.map(tool => [tool.name, Boolean(tool.available)]));
      result.innerHTML = plannedSteps.map((step, index) => {
        const ready = readiness.get(step.tool);
        const readyText = ready === false ? "未就绪" : ready === true ? "Ready" : "待检查";
        return `<article class="operator-plan-step"><span class="num">${String(index + 1).padStart(2,"0")}</span><div><strong>${esc(step.tool)} · ${esc(step.title)}</strong><p>${esc(step.operation)}</p><code>${esc(step.params)}</code></div><div class="gate ${step.approval ? "approval" : ""}"><b>${esc(step.risk)}</b><span>${readyText}</span></div></article>`;
      }).join("") + `<div class="operator-empty">Target: ${esc(target)} · 执行时仍会再次经过 Scope、Policy、Readiness 与 Approval 检查。</div>`;
      start.disabled = false;
    } catch (error) {
      result.innerHTML = `<div class="operator-empty">无法读取工具状态：${esc(error.message || error)}</div>`;
      start.disabled = true;
    }
  }

  function openPlanDialog(target = "") {
    const dialog = ensurePlanDialog();
    const input = dialog.querySelector("[data-plan-target]");
    const current = document.getElementById("mission-target")?.textContent?.trim();
    if (input) input.value = target || (current && current !== "—" ? current : "");
    dialog.showModal();
    if (input?.value) renderPlan(dialog);
  }

  function installHub() {
    if (path !== "/") return;
    document.body.classList.add("operator-overview");
    const overview = document.getElementById("overview");
    const statusGrid = document.getElementById("status-grid");
    if (!overview || !statusGrid || document.getElementById("operator-hub")) return;
    const hub = document.createElement("section");
    hub.id = "operator-hub";
    hub.className = "operator-hub";
    hub.innerHTML = `<div class="operator-hub-head"><div><h1>操作控制台</h1><p>流程固定：先授权 Scope → 生成计划 → 自动执行低风险步骤 → 查看实时工具操作与证据 → 需要时人工审批 → 归档/删除记录。</p></div><div class="operator-autonomy"><strong>自治模式：运行到治理边界</strong><span>Discovery 步骤自动连续执行；遇到 Approval、预算、工具故障或人工 Review 自动停下。</span></div></div>
      <div class="operator-actions">
        <button class="operator-action" id="operator-start" type="button"><b>▶</b><strong>1 · 开始任务</strong><small>创建 Target 与执行预算</small></button>
        <button class="operator-action plan" id="operator-plan" type="button"><b>✺</b><strong>2 · 生成测试计划</strong><small>先预览工具与操作，不执行</small></button>
        <a class="operator-action" href="/missions"><b>⌁</b><strong>3 · 实时执行</strong><small>看 Tool、argv、stdout、stderr</small></a>
        <a class="operator-action" href="/intelligence"><b>◉</b><strong>4 · 数据 / 证据</strong><small>看 Evidence、Facts、Findings</small></a>
        <a class="operator-action attention" href="/approval"><b>♙</b><strong>5 · 审批</strong><small>只处理等待人工批准的动作</small></a>
        <a class="operator-action" href="/chronicle"><b>▤</b><strong>6 · 记录 / 删除</strong><small>报告、历史、清理任务记录</small></a>
      </div>
      <div class="operator-current"><section class="operator-card"><div class="operator-card-head"><h2>当前任务 · 实际执行清单</h2><small>这里显示真正调用过/将调用的工具</small></div><div class="operator-card-body" id="operator-execution"><div class="operator-empty">正在读取任务…</div></div></section><aside class="operator-card"><div class="operator-card-head"><h2>现在该做什么</h2><small>Next action</small></div><div class="operator-card-body operator-next" id="operator-next"><div class="operator-empty">读取中…</div></div></aside></div>`;
    statusGrid.before(hub);
    document.getElementById("operator-start")?.addEventListener("click", () => {
      const source = document.getElementById("new-mission-btn") || document.getElementById("empty-new-mission-btn");
      source?.click();
    });
    document.getElementById("operator-plan")?.addEventListener("click", () => openPlanDialog());
  }

  function evidenceForStep(detail, step) {
    if (!step?.evidence_id) return null;
    return (detail.evidence || []).find(item => item.id === step.evidence_id) || null;
  }

  function firstOutput(evidence) {
    if (!evidence) return "尚未执行";
    const text = String(evidence.stdout || evidence.stderr || "").split(/\r?\n/).map(value => value.trim()).find(Boolean);
    return text ? text.slice(0, 150) : `exit ${evidence.exit_code}`;
  }

  async function refreshHub() {
    if (path !== "/") return;
    const exec = document.getElementById("operator-execution");
    const next = document.getElementById("operator-next");
    if (!exec || !next || document.hidden) return;
    try {
      const list = (await api("/api/missions")).missions || [];
      const selected = document.getElementById("mission-select")?.value;
      const runId = selected || list[0]?.id;
      if (!runId) {
        exec.innerHTML = `<div class="operator-empty">还没有任务。点击“开始任务”或先“生成测试计划”。</div>`;
        next.innerHTML = `<div class="operator-next-state"><strong>先建立第一个 Target</strong><p>如果是外部目标，先到“授权范围”加入 Scope。</p></div><a href="/scope">打开授权范围 →</a>`;
        return;
      }
      const detail = await api(`/api/missions/${encodeURIComponent(runId)}`);
      const rows = (detail.steps || []).map((step, index) => {
        const evidence = evidenceForStep(detail, step);
        const command = evidence ? `$ ${(evidence.argv || []).join(" ")}` : step.state === "waiting_approval" ? "等待批准后生成实际 argv" : "尚未执行";
        return `<tr><td>${String(index + 1).padStart(2,"0")}</td><td><strong>${esc(step.tool)}</strong><br><span>${esc(stateName(step.state))}</span></td><td><code title="${esc(command)}">${esc(command)}</code></td><td class="op-result">${esc(firstOutput(evidence))}</td><td>${evidence ? `exit ${esc(evidence.exit_code)}` : "—"}</td></tr>`;
      }).join("");
      exec.innerHTML = `<div class="operator-run-meta"><span class="operator-chip">Target <strong>${esc(detail.target)}</strong></span><span class="operator-chip">Run <strong>${esc(short(detail.id))}</strong></span><span class="operator-chip">State <strong>${esc(stateName(detail.state))}</strong></span><span class="operator-chip">Evidence <strong>${detail.evidence?.length || 0}</strong></span></div><table class="operator-exec-table"><thead><tr><th>#</th><th>Tool / State</th><th>实际命令</th><th>结果摘要</th><th>Exit</th></tr></thead><tbody>${rows || `<tr><td colspan="5">没有计划步骤。</td></tr>`}</tbody></table>`;
      const waiting = (detail.steps || []).find(step => step.state === "waiting_approval");
      const failed = (detail.steps || []).find(step => ["failed","denied"].includes(step.state));
      if (waiting) {
        next.innerHTML = `<div class="operator-next-state"><strong>需要人工审批：${esc(waiting.tool)}</strong><p>${esc(waiting.rationale || "高风险验证需要人工确认。")}</p></div><a href="/approval?run=${encodeURIComponent(detail.id)}">进入审批 →</a><a href="/missions?run=${encodeURIComponent(detail.id)}">先看完整执行证据 →</a>`;
      } else if (failed) {
        next.innerHTML = `<div class="operator-next-state"><strong>执行失败：${esc(failed.tool)}</strong><p>${esc(failed.error || "查看 stderr 与工具 readiness。")}</p></div><a href="/missions?run=${encodeURIComponent(detail.id)}">查看 stderr / Evidence →</a><a href="/tools">检查工具状态 →</a>`;
      } else if (detail.state === "running") {
        next.innerHTML = `<div class="operator-next-state"><strong>任务正在自动推进</strong><p>低风险步骤会继续执行，直到预算或治理边界。</p></div><a href="/missions?run=${encodeURIComponent(detail.id)}">打开实时执行 →</a>`;
      } else {
        next.innerHTML = `<div class="operator-next-state"><strong>本轮已结束：${esc(stateName(detail.state))}</strong><p>先看 Intelligence / Report，再决定是否创建下一轮计划。</p></div><a href="/intelligence?run=${encodeURIComponent(detail.id)}">查看结果数据 →</a><a href="/chronicle?run=${encodeURIComponent(detail.id)}">报告 / 删除记录 →</a>`;
      }
    } catch (error) {
      exec.innerHTML = `<div class="operator-empty">读取任务失败：${esc(error.message || error)}</div>`;
      next.innerHTML = `<div class="operator-empty">无法计算下一步。</div>`;
    }
  }

  installOperatorNav();
  installHub();
  if (path === "/") {
    refreshHub();
    setInterval(refreshHub, 4000);
    window.addEventListener("tonmen:runtime-event", () => setTimeout(refreshHub, 80));
    document.getElementById("mission-select")?.addEventListener("change", refreshHub);
  }
})();
