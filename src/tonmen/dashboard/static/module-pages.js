(() => {
  "use strict";

  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const overview = document.getElementById("overview");
  const stage = document.querySelector(".main-stage");
  if (!overview || !stage) return;

  const root = document.createElement("section");
  root.id = "module-page-root";
  root.className = "module-page-root";
  stage.appendChild(root);

  const pageState = {
    route: null,
    busy: false,
    rendering: false,
    renderPending: false,
    selectedRun: null,
    cache: {}
  };

  // 精简后的导航映射（与 index.html 侧边栏一致）
  const routeMap = [
    ["总览", "/"],
    ["任务", "/missions"],
    ["工具", "/tools"],
    ["主导", "/lead"],
    ["治理", "/guard"],
    ["设置", "/settings"]
  ];

  const titles = {
    "/missions": ["任务", "完整任务工作台", "查看所有任务、步骤、执行结果和原始输出。"],
    "/tools": ["工具", "已注册能力", "查看系统工具是否可用、风险等级和能力说明。"],
    "/lead": ["主导", "主导智能", "查看主导智能的当前指令、子代理分工和调用状态。"],
    "/guard": ["治理", "策略与审计", "策略规则、风险等级、审批边界和实时审计日志。"],
    "/settings": ["设置", "系统配置", "项目配置、运行目录和系统自检结果。"],
    // 以下保留旧路由兼容，直接访问仍可用
    "/scope": ["授权目标", "Scope", "授权目标与边界规则。"],
    "/intelligence": ["情报", "Intelligence", "从执行结果中解析出的有效信息。"],
    "/reasoner": ["决策", "Reasoner", "系统做出的决策和下一步建议。"],
    "/loop": ["循环", "Loop", "任务循环过程与停止原因。"],
    "/chronicle": ["记录", "Chronicle", "跨任务历史与审计。"],
    "/approval": ["审批队列", "Approval", "所有等待人工批准的步骤。"]
  };

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const nowText = () => new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"});
  const fmt = value => value ? new Date(value).toLocaleString() : "—";
  const short = value => String(value || "").slice(0, 8);
  const stateTone = state => state === "succeeded" ? "ok" : state === "waiting_approval" || state === "running" ? "warn" : state === "failed" || state === "denied" ? "bad" : "blue";
  const stateName = state => ({pending:"待执行",running:"运行中",waiting_approval:"等待审批",succeeded:"已完成",skipped:"已跳过",failed:"失败",denied:"已拒绝"}[state] || state);
  const toast = (message, bad = false) => {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message; el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.timer); toast.timer = setTimeout(() => { el.className = "toast"; }, 3000);
  };

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

  function normalizeRoute(pathname) {
    const value = pathname.replace(/\/+$/, "") || "/";
    return titles[value] || value === "/" ? value : "/";
  }

  function setNav(route) {
    document.querySelectorAll(".nav-item").forEach(button => {
      const text = button.textContent.trim();
      const match = routeMap.find(([label]) => text === label || text.startsWith(label));
      button.classList.toggle("active", Boolean(match && match[1] === route));
    });
  }

  function pageShell(route, body, actions = "") {
    const [zh, en, description] = titles[route] || ["页面", "", ""];
    return `<div class="module-page-head"><div><h1>${esc(zh)}</h1><p>${esc(description)}</p></div><div class="module-live"><span>实时更新 · <b id="module-updated">${nowText()}</b></span></div></div>${actions}${body}`;
  }

  function setPage(route, body, actions = "") {
    if (pageState.route !== route) return false;
    const signature = `${actions}\u0000${body}`;
    if (pageState.cache[route] === signature) return false;
    pageState.cache[route] = signature;
    root.innerHTML = pageShell(route, body, actions);
    bindCommonActions();
    return true;
  }

  function loading(route) {
    delete pageState.cache[route];
    root.innerHTML = pageShell(route, `<div class="module-card"><div class="module-empty"><b>正在加载…</b></div></div>`);
  }

  function errorPage(route, error) {
    delete pageState.cache[route];
    root.innerHTML = pageShell(route, `<div class="module-error">${esc(error.message || error)}</div>`);
  }

  async function missionList() { return (await api("/api/missions")).missions || []; }
  async function missionDetail(id) { return api(`/api/missions/${encodeURIComponent(id)}`); }
  async function recentDetails(limit = 12) {
    const list = (await missionList()).slice(0, limit);
    const rows = await Promise.allSettled(list.map(item => missionDetail(item.id)));
    return rows.filter(item => item.status === "fulfilled").map(item => item.value);
  }

  function stats(items) {
    const counts = items.reduce((acc, item) => { acc[item.state] = (acc[item.state] || 0) + 1; return acc; }, {});
    return `<div class="module-stat-grid">
      <div class="module-stat"><span>总计</span><strong>${items.length}</strong></div>
      <div class="module-stat"><span>运行中</span><strong>${counts.running || 0}</strong></div>
      <div class="module-stat"><span>等待审批</span><strong>${counts.waiting_approval || 0}</strong></div>
      <div class="module-stat"><span>失败/拒绝</span><strong>${(counts.failed || 0) + (counts.denied || 0)}</strong></div>
    </div>`;
  }

  function evidenceBlock(evidence) {
    if (!evidence?.length) return `<div class="module-empty"><b>暂无原始证据</b>执行完成后会显示输出内容。</div>`;
    return evidence.slice().reverse().map(item => `<div style="margin-bottom:9px"><div class="detail-title"><strong>${esc(item.tool)} · ${esc(short(item.id))}</strong><span class="module-badge ${item.exit_code === 0 ? "ok" : "bad"}">退出码 ${item.exit_code}</span></div><pre class="terminal"><span class="cmd">$ ${esc((item.argv || []).join(" "))}</span>\n\n<span class="stdout">--- 标准输出 ---\n${esc(item.stdout || "(空)")}</span>\n\n<span class="stderr">--- 错误输出 ---\n${esc(item.stderr || "(空)")}</span></pre></div>`).join("");
  }

  function stepsBlock(mission) {
    return `<div class="detail-steps">${(mission.steps || []).map((step, index) => `<div class="detail-step"><span class="num">${String(index + 1).padStart(2,"0")}</span><strong>${esc(step.tool)}</strong><div><code>${esc(step.target)}</code><br><small class="${step.error ? "err" : ""}">${esc(step.error || step.rationale || "")}</small></div><span class="module-badge ${stateTone(step.state)}">${esc(stateName(step.state))}</span></div>`).join("")}</div>`;
  }

  function actionToolbar(extra = "") {
    return `<div class="module-toolbar"><button class="primary" data-module-new>执行新任务</button><button class="ghost" data-module-refresh>刷新</button>${extra}</div>`;
  }

  async function downloadMissionPdf(runId) {
    if (!runId) return;
    toast("正在生成任务 PDF 报告...");
    try {
      const [missionRes, reportRes] = await Promise.allSettled([
        missionDetail(runId),
        fetch(`/api/missions/${encodeURIComponent(runId)}/report`, {cache:"no-store"}).then(r => r.ok ? r.json() : null)
      ]);
      const mission = missionRes.status === "fulfilled" ? missionRes.value : null;
      const report = reportRes.status === "fulfilled" ? reportRes.value : null;
      if (!mission) throw new Error("无法加载任务详情");

      const steps = mission.steps || [];
      const evidence = mission.evidence || [];
      const observations = mission.observations || [];

      const stepsHtml = steps.length ? steps.map((s, i) => `
        <div style="margin-bottom:12px; padding:10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px;">
          <strong>Step ${i + 1}: ${esc(s.tool)}</strong> (${esc(s.target)})<br>
          <span style="font-size:12px; color:#475569;">状态: ${esc(stateName(s.state))} | 风险: L${esc(s.risk || 1)}</span>
          ${s.rationale ? `<div style="margin-top:4px; font-size:13px; color:#334155;">策略/理由: ${esc(s.rationale)}</div>` : ""}
          ${s.error ? `<div style="margin-top:4px; font-size:13px; color:#dc2626;">错误: ${esc(s.error)}</div>` : ""}
        </div>
      `).join("") : `<p>暂无决策步骤记录</p>`;

      const evidenceHtml = evidence.length ? evidence.map(e => `
        <div style="margin-bottom:12px; border:1px solid #cbd5e1; border-radius:6px; overflow:hidden;">
          <div style="background:#f1f5f9; padding:8px 12px; font-size:13px; font-weight:600; display:flex; justify-content:space-between;">
            <span>Tool: ${esc(e.tool)} (${short(e.id)})</span>
            <span>Exit Code: ${e.exit_code}</span>
          </div>
          <div style="padding:8px 12px; font-family:monospace; font-size:12px; background:#0f172a; color:#e2e8f0; overflow-x:auto;">
            <div>$ ${(e.argv || []).join(" ")}</div>
            <div style="margin-top:6px; color:#93c5fd;">STDOUT:\n${esc(e.stdout || "(空)")}</div>
            ${e.stderr ? `<div style="margin-top:6px; color:#fca5a5;">STDERR:\n${esc(e.stderr)}</div>` : ""}
          </div>
        </div>
      `).join("") : `<p>暂无关键证据输出</p>`;

      const observationsHtml = observations.length ? observations.map(o => `
        <div style="margin-bottom:8px; padding:8px 12px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; font-size:13px; color:#166534;">
          <strong>[${esc(o.captured_at || "")}]</strong> ${esc(o.summary)}
        </div>
      `).join("") : `<p>暂无最终执行观测结果</p>`;

      const win = window.open("", "_blank");
      if (!win) {
        throw new Error("浏览器拦截了弹出窗口，请允许弹出窗口后重试");
      }

      win.document.write(`
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8">
          <title>云顶天宫 - 任务执行报告 (${esc(runId)})</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1e293b; margin: 0; padding: 24px; line-height: 1.5; background: #fff; }
            h1 { font-size: 22px; border-bottom: 2px solid #0284c7; padding-bottom: 8px; margin-bottom: 16px; color: #0f172a; }
            h2 { font-size: 16px; margin-top: 24px; margin-bottom: 12px; color: #0369a1; border-left: 4px solid #0284c7; padding-left: 8px; }
            .meta-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px; font-size: 14px; }
            .meta-item span { color: #64748b; font-size: 12px; display: block; }
            .meta-item strong { color: #0f172a; font-size: 14px; }
            @media print {
              body { padding: 0; }
              button { display: none !important; }
            }
          </style>
        </head>
        <body>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div>
              <h1 style="margin:0;">云顶天宫安全运行时 - 任务执行报告</h1>
              <p style="margin:4px 0 0; color:#64748b; font-size:13px;">Autonomous Security Runtime Mission Audit Report</p>
            </div>
            <button onclick="window.print()" style="background:#0284c7; color:#fff; border:none; padding:8px 16px; border-radius:6px; font-size:14px; cursor:pointer; font-weight:600;">打印 / 保存为 PDF</button>
          </div>

          <div class="meta-grid">
            <div class="meta-item"><span>任务编号 (Mission ID)</span><strong>${esc(mission.id)}</strong></div>
            <div class="meta-item"><span>目标 (Target)</span><strong>${esc(mission.target)}</strong></div>
            <div class="meta-item"><span>执行状态 (State)</span><strong>${esc(stateName(mission.state))}</strong></div>
            <div class="meta-item"><span>开始时间 (Started At)</span><strong>${esc(fmt(mission.started_at))}</strong></div>
          </div>

          <h2>1. 任务决策链路 (Decision Chain & Steps)</h2>
          ${stepsHtml}

          <h2>2. 关键证据链 (Key Evidence & Tool Output)</h2>
          ${evidenceHtml}

          <h2>3. 最终执行结果与观测 (Final Execution Results & Observations)</h2>
          ${observationsHtml}

          <div style="margin-top:40px; border-top:1px solid #e2e8f0; padding-top:12px; text-align:center; font-size:12px; color:#94a3b8;">
            云顶天宫安全运行时控制台 · 自动生成于 ${new Date().toLocaleString()}
          </div>
          <script>
            setTimeout(() => { window.print(); }, 400);
          </script>
        </body>
        </html>
      `);
      win.document.close();
      toast("PDF 报告生成窗口已打开");
    } catch (e) {
      toast(e.message || String(e), true);
    }
  }

  async function renderMissions() {
    const route = "/missions";
    const list = await missionList();
    const params = new URLSearchParams(location.search);
    let selected = params.get("run") || pageState.selectedRun || list[0]?.id || null;
    if (selected && !list.some(item => item.id === selected)) selected = list[0]?.id || null;
    pageState.selectedRun = selected;
    const detail = selected ? await missionDetail(selected) : null;
    const rows = list.map(item => `<tr class="selectable ${item.id === selected ? "selected" : ""}" data-select-run="${esc(item.id)}"><td>${esc(short(item.id))}</td><td>${esc(item.target)}</td><td><span class="module-badge ${stateTone(item.state)}">${esc(stateName(item.state))}</span></td><td>${esc(fmt(item.started_at))}</td><td><button type="button" class="ghost small" data-download-pdf="${esc(item.id)}" title="下载包含决策链路、关键证据与最终结果的 PDF 报告">下载 PDF 报告</button></td></tr>`).join("");
    const detailHtml = detail ? `
      <div class="module-card" style="margin-bottom: 12px; border-color: #38bdf8;">
        <div class="module-card-head">
          <h2>🧭 中途方向提示与实时干预 (Agent Prompt Steering)</h2>
          <small>在中途向此 LLM 任务代理实时注入策略导向、绕过技巧或攻击方向调整</small>
        </div>
        <div class="module-card-body" style="display: flex; flex-direction: column; gap: 8px;">
          <textarea id="mission-steering-input" rows="2" placeholder="输入中途方向提示，例如：&#10;1. 优先使用代理轮换绕过WAF限速&#10;2. 重点对目标 /api/v1/auth 进行盲打注入测验" style="padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 12px; background: #0f172a; color: #e2e8f0;"></textarea>
          <div>
            <button type="button" class="primary small" data-inject-mission-prompt="${esc(detail.id)}">🎯 发送方向提示给此任务代理</button>
          </div>
        </div>
      </div>
      <div class="detail-title"><div><strong>${esc(detail.target)}</strong><br><small>任务 ${esc(detail.id)}</small></div><span class="module-badge ${stateTone(detail.state)}">${esc(stateName(detail.state))}</span></div>${stepsBlock(detail)}<div style="height:10px"></div><div class="module-card"><div class="module-card-head"><h2>执行内容</h2></div><div class="module-card-body">${evidenceBlock(detail.evidence)}</div></div>` : `<div class="module-empty"><b>尚无任务</b>请先在总览页执行任务。</div>`;
    const changed = setPage(route, `${stats(list)}<div style="height:10px"></div><div class="module-grid two"><section class="module-card"><div class="module-card-head"><h2>任务列表</h2><small>${list.length} 个</small></div><div class="module-table-wrap"><table class="module-table"><thead><tr><th>编号</th><th>目标</th><th>状态</th><th>开始时间</th><th>操作</th></tr></thead><tbody>${rows || `<tr><td colspan="5">暂无任务</td></tr>`}</tbody></table></div></section><section class="module-card"><div class="module-card-head"><h2>任务详情</h2></div><div class="module-card-body">${detailHtml}</div></section></div>`, actionToolbar(detail?.state === "running" ? `<button class="primary" data-resume-run="${esc(detail.id)}">续行</button>` : detail?.state === "waiting_approval" ? `<button class="danger" data-approve-run="${esc(detail.id)}">批准当前步骤</button>` : detail?.state === "failed" ? `<button class="primary" data-retry-target="${esc(detail.target)}">重新执行</button>` : ""));
    if (changed) bindMissionSelection();
  }

  async function renderTools() {
    const route = "/tools";
    const data = await api("/api/tools");
    const cards = (data.tools || []).map(tool => `<article class="module-card tool-card"><div class="tool-card-top"><div><h3>${esc(tool.name)}</h3><span class="module-badge blue">${esc(tool.category)}</span></div><span class="module-badge ${tool.available ? "ok" : "bad"}">${tool.available ? "可用" : "不可用"}</span></div><p>${esc(tool.description)}</p><div class="fact-meta"><span class="module-badge ${tool.risk >= 3 ? "warn" : "ok"}">风险等级 ${tool.risk}</span></div></article>`).join("");
    setPage(route, `<div class="module-grid three">${cards || `<div class="module-empty">暂无工具</div>`}</div>`, actionToolbar());
  }

  async function renderLead() {
    const route = "/lead";
    const data = await api("/api/ai/lead");
    const cfg = data.config || {};
    setPage(route, `<div class="module-card"><div class="module-card-head"><h2>主导智能状态</h2></div><div class="module-card-body"><p>提供方：${esc(cfg.provider || "未启用")}</p><p>模型：${esc(cfg.model || "—")}</p><p>密钥已配置：${cfg.key_configured ? "是" : "否"}</p></div></div>`, actionToolbar());
  }

  async function renderGuard() {
    const route = "/guard";
    const data = await api("/api/guard");
    setPage(route, `<div class="module-stat-grid">
      <div class="module-stat"><span>模式</span><strong>${esc(data.mode)}</strong></div>
      <div class="module-stat"><span>等待审批</span><strong>${data.pending_approvals || 0}</strong></div>
    </div>
    <div style="height:10px"></div>
    <section class="module-card"><div class="module-card-head"><h2>策略规则</h2></div><div class="module-card-body">${(data.rules || []).map(r => `<div class="policy-rule"><strong>${esc(r.name)}</strong> · ${esc(r.decision)} · ${esc(r.detail)}</div>`).join("")}</div></section>`, actionToolbar());
  }

  async function renderSettings() {
    const route = "/settings";
    const [settings, status] = await Promise.all([api("/api/settings"), api("/api/status")]);
    const fields = Object.entries(settings).map(([key,value]) => `<dt>${esc(key)}</dt><dd>${esc(Array.isArray(value) ? value.join(", ") : value)}</dd>`).join("");
    setPage(route, `<div class="module-grid two"><section class="module-card"><div class="module-card-head"><h2>项目配置</h2></div><div class="module-card-body"><dl class="settings-grid">${fields}</dl></div></section><section class="module-card"><div class="module-card-head"><h2>系统自检</h2><span class="module-badge ${status.doctor?.ready ? "ok" : "warn"}">${status.doctor?.ready ? "正常" : "需检查"}</span></div></section></div>`, actionToolbar());
  }

  // 兼容旧路由的简单渲染
  async function renderScope() { const data = await api("/api/scope"); setPage("/scope", `<div class="module-card"><div class="module-card-body">${(data.allowed||[]).map(i=>`<div>${esc(i.rule)}</div>`).join("")||"暂无"}</div></div>`, actionToolbar()); }
  async function renderIntelligence() { setPage("/intelligence", `<div class="module-empty">情报内容已合并到「任务」模块，请前往任务页查看。</div>`, actionToolbar()); }
  async function renderReasoner() { setPage("/reasoner", `<div class="module-empty">决策内容已合并到「任务」模块，请前往任务页查看。</div>`, actionToolbar()); }
  async function renderLoop() { setPage("/loop", `<div class="module-empty">循环内容已合并到「任务」模块，请前往任务页查看。</div>`, actionToolbar()); }
  async function renderChronicle() { setPage("/chronicle", `<div class="module-empty">记录已合并到总览「实时动态记录」和「任务」模块。</div>`, actionToolbar()); }
  async function renderApproval() { setPage("/approval", `<div class="module-empty">审批已合并到总览页，请返回总览处理。</div>`, actionToolbar()); }

  const renderers = {
    "/missions": renderMissions,
    "/tools": renderTools,
    "/lead": renderLead,
    "/guard": renderGuard,
    "/settings": renderSettings,
    "/scope": renderScope,
    "/intelligence": renderIntelligence,
    "/reasoner": renderReasoner,
    "/loop": renderLoop,
    "/chronicle": renderChronicle,
    "/approval": renderApproval
  };

  async function renderRoute(force = false) {
    if (pageState.rendering) {
      pageState.renderPending = true;
      return;
    }
    pageState.rendering = true;
    try {
      const route = normalizeRoute(location.pathname);
      pageState.route = route;
      setNav(route);
      if (route === "/") {
        overview.classList.remove("module-hidden");
        root.classList.remove("active");
        root.innerHTML = "";
        document.title = "雲頂天宮 | 云顶天宫控制台";
        return;
      }
      overview.classList.add("module-hidden");
      root.classList.add("active");
      document.title = `${(titles[route] || ["页面"])[0]} | 云顶天宫控制台`;
      if (!force) loading(route);
      try {
        await (renderers[route] || renderMissions)();
      } catch (error) {
        if (pageState.route === route) errorPage(route, error);
      }
    } finally {
      pageState.rendering = false;
      if (pageState.renderPending) {
        pageState.renderPending = false;
        queueMicrotask(() => renderRoute(true));
      }
    }
  }

  function navigate(route, query = "") {
    const url = `${route}${query}`;
    if (`${location.pathname}${location.search}` !== url) history.pushState({}, "", url);
    renderRoute();
  }

  function bindMissionSelection() {
    root.querySelectorAll("[data-select-run]").forEach(row => row.addEventListener("click", () => {
      pageState.selectedRun = row.dataset.selectRun;
      history.replaceState({}, "", `/missions?run=${encodeURIComponent(pageState.selectedRun)}`);
      renderRoute();
    }));
    root.querySelectorAll("[data-download-pdf]").forEach(btn => btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const runId = btn.dataset.downloadPdf;
      await downloadMissionPdf(runId);
    }));
    root.querySelectorAll("[data-inject-mission-prompt]").forEach(btn => btn.addEventListener("click", async () => {
      const runId = btn.dataset.injectMissionPrompt;
      const textarea = document.getElementById("mission-steering-input");
      const prompt_direction = textarea ? textarea.value.trim() : "";
      if (!prompt_direction) {
        toast("请先输入方向提示内容", true);
        return;
      }
      try {
        pageState.busy = true;
        toast("正在注入中途方向提示...");
        await api(`/api/missions/${encodeURIComponent(runId)}/inject-prompt`, {
          method: "POST",
          body: { prompt_direction }
        });
        toast("成功向 LLM 任务注入方向提示！代理已动态调整策略。");
        await renderRoute(true);
      } catch (err) {
        toast(err.message || String(err), true);
      } finally {
        pageState.busy = false;
      }
    }));
  }

  function bindOpenRun() {
    root.querySelectorAll("[data-open-run]").forEach(button => button.addEventListener("click", () => navigate("/missions", `?run=${encodeURIComponent(button.dataset.openRun)}`)));
  }

  function bindCommonActions() {
    root.querySelectorAll("[data-module-refresh]").forEach(button => button.addEventListener("click", () => renderRoute(true)));
    root.querySelectorAll("[data-module-new]").forEach(button => button.addEventListener("click", () => {
      document.getElementById("deck-new-mission")?.click() || document.getElementById("new-mission-btn")?.click();
    }));
    root.querySelectorAll("[data-route-go]").forEach(button => button.addEventListener("click", () => navigate(button.dataset.routeGo)));
    root.querySelectorAll("[data-retry-target]").forEach(button => button.addEventListener("click", () => {
      document.getElementById("deck-new-mission")?.click();
      setTimeout(() => { const input = document.getElementById("mission-input"); if (input) input.value = button.dataset.retryTarget; }, 30);
    }));
    root.querySelectorAll("[data-resume-run]").forEach(button => button.addEventListener("click", async () => {
      try {
        pageState.busy = true;
        toast("正在续行…");
        await api(`/api/missions/${encodeURIComponent(button.dataset.resumeRun)}/resume`, {method:"POST",body:{}});
        await renderRoute(true);
        toast("任务已续行");
      } catch (error) { toast(error.message, true); }
      finally { pageState.busy = false; }
    }));
    root.querySelectorAll("[data-approve-run]").forEach(button => button.addEventListener("click", async () => {
      if (!confirm("确认批准此步骤？批准仅绑定当前工具和目标，且为一次性。")) return;
      try {
        pageState.busy = true;
        toast("正在执行批准…");
        await api(`/api/missions/${encodeURIComponent(button.dataset.approveRun)}/approve`, {method:"POST",body:{}});
        await renderRoute(true);
        toast("审批已完成");
      } catch (error) { toast(error.message, true); }
      finally { pageState.busy = false; }
    }));
    bindOpenRun();
  }

  document.addEventListener("click", event => {
    const button = event.target.closest?.(".nav-item");
    if (!button) return;
    const text = button.textContent.trim();
    const match = routeMap.find(([label]) => text === label || text.startsWith(label));
    if (!match) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    navigate(match[1]);
  }, true);

  window.addEventListener("popstate", () => renderRoute());
  setInterval(() => {
    if (document.hidden || pageState.busy || pageState.rendering || pageState.route === "/") return;
    renderRoute(true);
  }, 15000);

  renderRoute();
})();
