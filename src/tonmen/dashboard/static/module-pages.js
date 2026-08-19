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

  const pageState = { route: null, busy: false, selectedRun: null, cache: {} };
  const routeMap = [
    ["儀表總覽", "/"], ["任務", "/missions"], ["天域", "/scope"], ["天律", "/guard"],
    ["天工", "/tools"], ["天鑑", "/intelligence"], ["天策", "/reasoner"], ["主導", "/lead"], ["天衡", "/loop"],
    ["天冊", "/chronicle"], ["審批", "/approval"], ["設定", "/settings"]
  ];
  const titles = {
    "/missions": ["任務", "Missions", "任务、步骤、执行参数与原始输出的完整工作台。"],
    "/scope": ["天域", "Scope", "授权目标与边界规则；所有执行前都由此范围约束。"],
    "/guard": ["天律", "Guard", "策略、风险等级、审批边界与实时审计事件。"],
    "/tools": ["天工", "Tools", "Registry 中已注册能力、安装状态、风险与能力声明。"],
    "/intelligence": ["天鑑", "Intelligence", "从 Evidence 确定解析出的 Host / Service / Web / Finding。"],
    "/reasoner": ["天策", "Reasoner", "每次决策、依据 Fact、下一步与是否需要人工介入。"],
    "/lead": ["主導", "Lead AI", "单一主导智能层：为每轮 Council 定焦、统筹 3–5 子代理并记录模型调用状态；没有执行、审批或扩 Scope 权限。"],
    "/loop": ["天衡", "Mission Loop", "循环 Session、Iteration、Stop 原因、预算与当前执行状态。"],
    "/chronicle": ["天冊", "Chronicle", "跨任务历史、执行审计、Evidence 与时间线。"],
    "/approval": ["審批", "Approval", "所有等待人工审批的步骤集中处理，并在批准前查看证据。"],
    "/settings": ["設定", "Settings", "当前项目配置、运行目录、Console 与 Doctor 状态。"]
  };

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const nowText = () => new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"});
  const fmt = value => value ? new Date(value).toLocaleString() : "—";
  const short = value => String(value || "").slice(0, 8);
  const stateTone = state => state === "succeeded" ? "ok" : state === "waiting_approval" || state === "running" ? "warn" : state === "failed" || state === "denied" ? "bad" : "blue";
  const stateName = state => ({pending:"待行",running:"运行",waiting_approval:"候旨",succeeded:"完成",skipped:"跳过",failed:"失败",denied:"拒绝"}[state] || state);
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
      const match = routeMap.find(([label]) => text.startsWith(label));
      button.classList.toggle("active", Boolean(match && match[1] === route));
    });
  }

  function pageShell(route, body, actions = "") {
    const [zh, en, description] = titles[route];
    return `<div class="module-page-head"><div><span class="kicker">DETAILED WORKSPACE</span><h1>${esc(zh)} <small>/ ${esc(en)}</small></h1><p>${esc(description)}</p></div><div class="module-live"><i></i><span>EVENT STREAM · 2.5s fallback · <b id="module-updated">${nowText()}</b></span></div></div>${actions}${body}`;
  }

  function setPage(route, body, actions = "") {
    if (pageState.route !== route) return;
    root.innerHTML = pageShell(route, body, actions);
    bindCommonActions();
  }

  function loading(route) {
    root.innerHTML = pageShell(route, `<div class="module-card"><div class="module-empty"><b>读取实时数据…</b>正在连接 TONMEN Core。</div></div>`);
  }

  function errorPage(route, error) {
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
    return `<div class="module-stat-grid"><div class="module-stat"><span>Total</span><strong>${items.length}</strong></div><div class="module-stat"><span>Running</span><strong>${counts.running || 0}</strong></div><div class="module-stat"><span>Waiting approval</span><strong>${counts.waiting_approval || 0}</strong></div><div class="module-stat"><span>Failed / denied</span><strong>${(counts.failed || 0) + (counts.denied || 0)}</strong></div></div>`;
  }

  function evidenceBlock(evidence) {
    if (!evidence?.length) return `<div class="module-empty"><b>暂无原始 Evidence</b>执行完成后 stdout / stderr 会显示在这里。</div>`;
    return evidence.slice().reverse().map(item => `<div style="margin-bottom:9px"><div class="detail-title"><strong>${esc(item.tool)} · ${esc(short(item.id))}</strong><span class="module-badge ${item.exit_code === 0 ? "ok" : "bad"}">exit ${item.exit_code}</span></div><pre class="terminal"><span class="cmd">$ ${esc((item.argv || []).join(" "))}</span>\n\n<span class="stdout">--- stdout ---\n${esc(item.stdout || "(empty)")}</span>\n\n<span class="stderr">--- stderr ---\n${esc(item.stderr || "(empty)")}</span></pre></div>`).join("");
  }

  function stepsBlock(mission) {
    return `<div class="detail-steps">${(mission.steps || []).map((step, index) => `<div class="detail-step"><span class="num">${String(index + 1).padStart(2,"0")}</span><strong>${esc(step.tool)}</strong><div><code>${esc(step.target)}</code><br><small class="${step.error ? "err" : ""}">${esc(step.error || step.rationale || "")}</small></div><span class="module-badge ${stateTone(step.state)}">${esc(stateName(step.state))}</span></div>`).join("")}</div>`;
  }

  function actionToolbar(extra = "") {
    return `<div class="module-toolbar"><button class="primary" data-module-new>▶ 执行新任务</button><button class="ghost" data-module-refresh>↻ 刷新实时数据</button>${extra}</div>`;
  }

  async function renderMissions() {
    const route = "/missions";
    const list = await missionList();
    const params = new URLSearchParams(location.search);
    let selected = params.get("run") || pageState.selectedRun || list[0]?.id || null;
    if (selected && !list.some(item => item.id === selected)) selected = list[0]?.id || null;
    pageState.selectedRun = selected;
    const detail = selected ? await missionDetail(selected) : null;
    const rows = list.map(item => `<tr class="selectable ${item.id === selected ? "selected" : ""}" data-select-run="${esc(item.id)}"><td>${esc(short(item.id))}</td><td>${esc(item.target)}</td><td><span class="module-badge ${stateTone(item.state)}">${esc(stateName(item.state))}</span></td><td>${esc(fmt(item.started_at))}</td></tr>`).join("");
    const detailHtml = detail ? `<div class="detail-title"><div><strong>${esc(detail.target)}</strong><br><small>Run ${esc(detail.id)} · Plan ${esc(detail.plan_id)}</small></div><span class="module-badge ${stateTone(detail.state)}">${esc(stateName(detail.state))}</span></div>${stepsBlock(detail)}<div style="height:10px"></div><div class="module-card"><div class="module-card-head"><h2>执行内容 / Execution Content</h2><small>argv · stdout · stderr</small></div><div class="module-card-body">${evidenceBlock(detail.evidence)}</div></div>` : `<div class="module-empty"><b>尚无任务</b>从主界面或这里建立第一项受治理任务。</div>`;
    setPage(route, `${stats(list)}<div style="height:10px"></div><div class="module-grid two"><section class="module-card"><div class="module-card-head"><h2>任务历史</h2><small>${list.length} runs</small></div><div class="module-table-wrap"><table class="module-table"><thead><tr><th>Run</th><th>Target</th><th>State</th><th>Started</th></tr></thead><tbody>${rows || `<tr><td colspan="4">暂无任务</td></tr>`}</tbody></table></div></section><section class="module-card"><div class="module-card-head"><h2>任务详情</h2><small>实时步骤与输出</small></div><div class="module-card-body">${detailHtml}</div></section></div>`, actionToolbar(detail?.state === "running" ? `<button class="primary" data-resume-run="${esc(detail.id)}">∞ 续行</button>` : detail?.state === "waiting_approval" ? `<button class="danger" data-approve-run="${esc(detail.id)}">✓ 批准当前步骤</button>` : detail?.state === "failed" ? `<button class="primary" data-retry-target="${esc(detail.target)}">↻ 重跑</button>` : ""));
    bindMissionSelection();
  }

  async function renderScope() {
    const route = "/scope";
    const data = await api("/api/scope");
    const allowed = (data.allowed || []).map(item => `<div class="scope-detailed-row"><span class="scope-icon">${item.rule.includes("/") ? "⌘" : item.rule.startsWith("*.") ? "◎" : "◉"}</span><div><strong>${esc(item.rule)}</strong><small>${item.default ? "Built-in loopback authority" : "Project-authorized target"}</small></div><span class="module-badge ${item.default ? "blue" : "ok"}">${item.default ? "内建" : "已授权"}</span>${item.default ? "<span></span>" : `<button class="scope-remove" data-scope-remove="${esc(item.rule)}">移除</button>`}</div>`).join("");
    const denied = (data.denied || []).map(rule => `<div class="scope-detailed-row"><span class="scope-icon">×</span><div><strong>${esc(rule)}</strong><small>Explicit deny rule</small></div><span class="module-badge bad">拒绝</span><span></span></div>`).join("");
    const toolbar = `<div class="module-toolbar"><form data-scope-form style="display:flex;gap:7px;flex:1;flex-wrap:wrap"><input name="target" placeholder="host / URL / CIDR / *.domain" required><button class="primary" type="submit">＋ 纳入授权范围</button></form><button class="ghost" data-module-refresh>↻ 刷新</button></div>`;
    setPage(route, `<div class="module-grid two"><section class="module-card"><div class="module-card-head"><h2>Allowed Scope</h2><small>${data.allowed?.length || 0} rules</small></div><div>${allowed || `<div class="module-empty">暂无授权规则</div>`}</div></section><section class="module-card"><div class="module-card-head"><h2>Denied Scope</h2><small>deny overrides allow</small></div><div>${denied || `<div class="module-empty"><b>无显式拒绝规则</b>范围外目标仍然默认拒绝。</div>`}</div></section></div>`, toolbar);
    bindScopeActions();
  }

  async function renderGuard() {
    const route = "/guard";
    const data = await api("/api/guard");
    const risks = (data.risk_levels || []).map(item => `<div class="risk-level"><b>L${item.level}</b><span>${esc(item.name)}</span></div>`).join("");
    const rules = (data.rules || []).map(rule => `<div class="policy-rule"><strong>${esc(rule.name)}</strong><span class="module-badge ${rule.decision === "allow" ? "ok" : rule.decision === "approval" ? "warn" : "bad"}">${esc(rule.decision)}</span><span>${esc(rule.detail)}</span></div>`).join("");
    const audit = renderAudit(data.audit?.events || []);
    setPage(route, `<div class="module-stat-grid"><div class="module-stat"><span>Mode</span><strong>${esc(data.mode)}</strong></div><div class="module-stat"><span>Allowed rules</span><strong>${data.scope?.allowed?.length || 0}</strong></div><div class="module-stat"><span>Denied rules</span><strong>${data.scope?.denied?.length || 0}</strong></div><div class="module-stat"><span>Pending approvals</span><strong>${data.pending_approvals || 0}</strong></div></div><div style="height:10px"></div><div class="module-grid two"><section class="module-card"><div class="module-card-head"><h2>Policy Rules</h2><small>Scope → Risk → Approval</small></div><div>${rules}</div><div class="module-card-body"><div class="risk-ladder">${risks}</div></div></section><section class="module-card"><div class="module-card-head"><h2>实时审计 / Live Audit</h2><small>${esc(data.audit?.path || "")}</small></div><div class="module-card-body"><div class="audit-list">${audit}</div></div></section></div>`, actionToolbar(`<button class="ghost" data-route-go="/approval">打开审批中心</button>`));
  }

  async function renderTools() {
    const route = "/tools";
    const data = await api("/api/tools");
    const cards = (data.tools || []).map(tool => `<article class="module-card tool-card"><div class="tool-card-top"><div><h3>${esc(tool.name)}</h3><span class="module-badge blue">${esc(tool.category)}</span></div><span class="module-badge ${tool.available ? "ok" : "bad"}">${tool.available ? "AVAILABLE" : "MISSING"}</span></div><p>${esc(tool.description)}</p><div class="fact-meta"><span class="module-badge ${tool.risk >= 3 ? "warn" : "ok"}">L${tool.risk} ${esc(tool.risk_name)}</span>${tool.doctor?.detail ? `<span class="module-badge">${esc(tool.doctor.detail)}</span>` : ""}</div><div class="caps">${(tool.capabilities || []).map(cap => `<span>${esc(cap)}</span>`).join("")}</div></article>`).join("");
    setPage(route, `<div class="module-grid three">${cards || `<div class="module-empty">Registry 为空。</div>`}</div>`, actionToolbar());
  }

  async function renderIntelligence() {
    const route = "/intelligence";
    const details = await recentDetails(20);
    const facts = details.flatMap(run => (run.intelligence || []).map(node => ({...node, run_id:run.id, run_target:run.target})));
    const items = facts.slice().reverse().map(node => { const kind = node.kind.replace("intelligence.", ""); const severity = node.metadata?.severity; return `<article class="fact-item"><h3>${esc(node.label)}</h3><p>${esc(node.metadata?.target || node.run_target || "")}</p><div class="fact-meta"><span class="module-badge purple">${esc(kind)}</span>${severity ? `<span class="module-badge ${severity === "high" || severity === "critical" ? "bad" : severity === "medium" ? "warn" : "blue"}">${esc(severity)}</span>` : ""}<span class="module-badge">Evidence ${esc(short(node.metadata?.evidence_id))}</span><button class="ghost small" data-open-run="${esc(node.run_id)}">Run ${esc(short(node.run_id))}</button></div></article>`; }).join("");
    const kinds = facts.reduce((a,n)=>{const k=n.kind.replace("intelligence.","");a[k]=(a[k]||0)+1;return a;},{});
    setPage(route, `<div class="module-stat-grid"><div class="module-stat"><span>Facts</span><strong>${facts.length}</strong></div><div class="module-stat"><span>Services</span><strong>${kinds.service || 0}</strong></div><div class="module-stat"><span>Web</span><strong>${kinds.web || 0}</strong></div><div class="module-stat"><span>Findings</span><strong>${kinds.finding || 0}</strong></div></div><div style="height:10px"></div><section class="module-card"><div class="module-card-head"><h2>Evidence-backed Facts</h2><small>最近 20 个任务 · 自动刷新</small></div><div class="module-card-body"><div class="fact-list">${items || `<div class="module-empty"><b>暂无 Intelligence Fact</b>未解析的工具输出只保留为 Evidence，不会被猜测成事实。</div>`}</div></div></section>`, actionToolbar());
    bindOpenRun();
  }

  async function renderReasoner() {
    const route = "/reasoner";
    const details = await recentDetails(20);
    const decisions = details.flatMap(run => (run.reasoning || []).map(node => ({...node, run_id:run.id, run_target:run.target})));
    const items = decisions.slice().reverse().map(node => { const action = node.metadata?.action || node.kind.replace("reasoning.",""); const human = node.metadata?.requires_human; const basis = node.metadata?.basis_fact_ids || []; return `<article class="decision-item"><h3>${esc(action.toUpperCase())} · ${esc(node.run_target)}</h3><p>${esc(node.label)}</p><div class="decision-meta"><span class="module-badge ${human ? "warn" : "ok"}">${human ? "需人决" : "可自治"}</span><span class="module-badge purple">${basis.length} facts</span>${node.metadata?.next_step_id ? `<span class="module-badge">next ${esc(short(node.metadata.next_step_id))}</span>` : ""}<button class="ghost small" data-open-run="${esc(node.run_id)}">查看任务</button></div></article>`; }).join("");
    setPage(route, `<section class="module-card"><div class="module-card-head"><h2>天策决策历史</h2><small>Fact → Decision → Existing Step</small></div><div class="module-card-body"><div class="decision-list">${items || `<div class="module-empty"><b>暂无决策</b>任务产生证据后，Reasoner 决策会显示在这里。</div>`}</div></div></section>`, actionToolbar());
    bindOpenRun();
  }

  async function renderLead() {
    const route = "/lead";
    const data = await api("/api/ai/lead");
    const cfg = data.config || {};
    const current = data.current;
    const providerTone = cfg.active ? "ok" : cfg.provider === "openai" ? "warn" : "blue";
    const configError = cfg.error ? `<div class="lead-alert">${esc(cfg.error)}</div>` : "";
    const configCard = `<section class="module-card lead-config-card"><div class="module-card-head"><h2>Lead Runtime</h2><span class="module-badge ${providerTone}">${cfg.active ? "MODEL ACTIVE" : cfg.provider === "openai" ? "FALLBACK" : "DISABLED"}</span></div><div class="module-card-body"><div class="lead-kv"><span>Provider</span><strong>${esc(cfg.provider || "disabled")}</strong><span>Model</span><strong>${esc(cfg.model || "—")}</strong><span>Key configured</span><strong>${cfg.key_configured ? "yes" : "no"}</strong><span>Key env</span><code>${esc(cfg.key_env || "OPENAI_API_KEY")}</code><span>Secret persisted</span><strong>no</strong><span>Raw evidence sent</span><strong>no</strong></div>${configError}${!cfg.active ? `<pre class="lead-setup">export TONMEN_AI_PROVIDER=openai\nexport OPENAI_API_KEY=...\nexport TONMEN_AI_MODEL=${esc(cfg.model || "gpt-5.6")}</pre>` : ""}</div></section>`;

    if (!current) {
      setPage(route, `<div class="module-stat-grid"><div class="module-stat"><span>Lead state</span><strong>${cfg.active ? "ACTIVE" : "FALLBACK"}</strong></div><div class="module-stat"><span>Provider</span><strong>${esc(cfg.provider || "disabled")}</strong></div><div class="module-stat"><span>Model</span><strong>${esc(cfg.model || "—")}</strong></div><div class="module-stat"><span>Current mission</span><strong>NONE</strong></div></div><div style="height:10px"></div>${configCard}<div style="height:10px"></div><section class="module-card"><div class="module-empty"><b>尚无 Lead Directive</b>新任务进入 Assessment Council 后，这里会显示每轮主导目标和子代理编排。</div></section>`, actionToolbar());
      return;
    }

    const mission = current.mission || {};
    const directive = current.latest_directive || {};
    const md = directive.metadata || {};
    const telemetry = current.telemetry || {};
    const agents = current.subagents || [];
    const pct = Math.min(100, Math.round(((current.rounds_completed || 0) / Math.max(1, current.target_rounds || 8)) * 100));
    const sourceTone = md.source === "model" ? "ok" : md.error ? "warn" : "blue";
    const agentRows = agents.map(agent => { const am = agent.metadata || {}; return `<tr><td><strong>${esc(am.role || "subagent")}</strong></td><td>${esc(am.focus || md.focus || "—")}</td><td>${esc(am.recommended_action || "—")}</td><td>${esc((am.summary || agent.label || "").slice(0,500))}</td></tr>`; }).join("");
    const directiveCard = `<section class="module-card lead-directive-card"><div class="module-card-head"><div><h2>当前主导指令 / Current Directive</h2><small>Round ${esc(md.round || current.rounds_completed || "—")} · ${esc(md.phase || "—")}</small></div><span class="module-badge ${sourceTone}">${esc((md.source || "deterministic").toUpperCase())}</span></div><div class="module-card-body"><div class="lead-directive-head"><div><span>Focus</span><strong>${esc(md.focus || "—")}</strong></div><div><span>Recommended action</span><strong>${esc(md.recommended_action || "—")}</strong></div><div><span>Confidence</span><strong>${esc(md.confidence ?? "—")}</strong></div></div><h3>Objective</h3><p>${esc(md.objective || "—")}</p><h3>Rationale</h3><p>${esc(md.rationale || "—")}</p>${md.error ? `<div class="lead-alert">Fallback / error: ${esc(md.error)}</div>` : ""}</div></section>`;
    const progress = `<section class="module-card"><div class="module-card-head"><h2>Council Progress</h2><small>${current.rounds_completed || 0}/${current.target_rounds || 8} rounds · ${current.subagents_per_round || 4} subagents/round</small></div><div class="module-card-body"><div class="lead-progress"><i style="width:${pct}%"></i></div><div class="lead-progress-label"><span>${pct}% reviewed</span><span>Mission ${esc(short(mission.id))} · ${esc(stateName(mission.state))}</span></div></div></section>`;
    const telemetryCard = `<section class="module-card"><div class="module-card-head"><h2>调用遥测 / Telemetry</h2><small>不含 API Key</small></div><div class="module-card-body"><div class="lead-metric-grid"><div><span>Directives</span><strong>${telemetry.directives || 0}</strong></div><div><span>Model calls</span><strong>${telemetry.model_calls || 0}</strong></div><div><span>Fallbacks</span><strong>${telemetry.fallback_calls || 0}</strong></div><div><span>Total tokens</span><strong>${telemetry.total_tokens || 0}</strong></div><div><span>Last latency</span><strong>${telemetry.last_latency_ms ?? "—"} ms</strong></div><div><span>Avg latency</span><strong>${telemetry.latency_ms_average ?? "—"} ms</strong></div></div><div class="lead-token-line">input ${telemetry.input_tokens || 0} · output ${telemetry.output_tokens || 0} · total ${telemetry.total_tokens || 0}</div></div></section>`;
    const boundaries = `<section class="module-card"><div class="module-card-head"><h2>Authority Boundary</h2><span class="module-badge ok">GOVERNED</span></div><div class="module-card-body"><div class="lead-boundaries"><span>执行权 <b>NO</b></span><span>审批权 <b>NO</b></span><span>扩 Scope <b>NO</b></span><span>改计划 <b>NO</b></span><span>Raw Evidence <b>LOCAL</b></span><span>API Key <b>SERVER ONLY</b></span></div></div></section>`;
    const agentsCard = `<section class="module-card lead-agents-card"><div class="module-card-head"><h2>本轮子代理 / Subagents</h2><small>Lead → Council → ${agents.length} reviewers</small></div><div class="module-table-wrap"><table class="module-table"><thead><tr><th>Role</th><th>Focus</th><th>Recommendation</th><th>Review</th></tr></thead><tbody>${agentRows || `<tr><td colspan="4">当前轮次暂无子代理记录。</td></tr>`}</tbody></table></div></section>`;

    setPage(route, `<div class="module-stat-grid"><div class="module-stat"><span>Lead</span><strong>${md.source === "model" ? "MODEL" : "FALLBACK"}</strong></div><div class="module-stat"><span>Mission</span><strong>${esc(short(mission.id))}</strong></div><div class="module-stat"><span>Round</span><strong>${current.rounds_completed || 0}/${current.target_rounds || 8}</strong></div><div class="module-stat"><span>Subagents</span><strong>${agents.length}</strong></div></div><div style="height:10px"></div><div class="lead-console-grid">${configCard}${progress}${directiveCard}${telemetryCard}${boundaries}${agentsCard}</div>`, actionToolbar(`<button class="ghost" data-open-run="${esc(mission.id)}">查看当前任务</button>`));
    bindOpenRun();
  }

  async function renderLoop() {
    const route = "/loop";
    const details = await recentDetails(15);
    const current = details.find(run => run.state === "running" || run.state === "waiting_approval") || details[0] || null;
    const nodes = details.flatMap(run => (run.loop || []).map(node => ({...node, run_id:run.id, run_target:run.target})));
    const items = nodes.slice().reverse().map(node => `<article class="loop-item"><h3>${esc(node.kind.replace("loop.","").toUpperCase())} · ${esc(node.run_target)}</h3><p>${esc(node.label)}</p><div class="loop-meta">${Object.entries(node.metadata || {}).slice(0,7).map(([k,v]) => `<span class="module-badge">${esc(k)}=${esc(Array.isArray(v) ? v.join(",") : v)}</span>`).join("")}<button class="ghost small" data-open-run="${esc(node.run_id)}">任务</button></div></article>`).join("");
    const extra = current?.state === "running" ? `<button class="primary" data-resume-run="${esc(current.id)}">∞ 新预算续行</button>` : current?.state === "waiting_approval" ? `<button class="danger" data-route-go="/approval">转到人工审批</button>` : "";
    setPage(route, `${current ? `<div class="module-card"><div class="module-card-head"><h2>当前循环</h2><span class="module-badge ${stateTone(current.state)}">${esc(stateName(current.state))}</span></div><div class="module-card-body"><div class="detail-title"><strong>${esc(current.target)}</strong><small>${esc(current.id)}</small></div>${stepsBlock(current)}</div></div><div style="height:10px"></div>` : ""}<section class="module-card"><div class="module-card-head"><h2>Loop Provenance</h2><small>session · iteration · stop</small></div><div class="module-card-body"><div class="loop-list">${items || `<div class="module-empty">暂无 Loop provenance。</div>`}</div></div></section>`, actionToolbar(extra));
    bindOpenRun();
  }

  function renderAudit(events) {
    if (!events.length) return `<div class="module-empty"><b>暂无审计事件</b>执行与策略决定会出现在这里。</div>`;
    return events.slice().reverse().map(event => `<div class="audit-item ${esc(event.decision || "")}"><span class="time">${esc(fmt(event.timestamp))}</span><span>${esc(event.tool || "—")}</span><span class="decision">${esc(event.decision || "—")}</span><span class="message">${esc(event.target || "")} · ${esc(event.message || event.action || "")}</span></div>`).join("");
  }

  async function renderChronicle() {
    const route = "/chronicle";
    const [missions, audit] = await Promise.all([missionList(), api("/api/audit?limit=300")]);
    const history = missions.map(run => `<tr class="selectable" data-open-run="${esc(run.id)}"><td>${esc(fmt(run.started_at))}</td><td>${esc(run.target)}</td><td>${esc(short(run.id))}</td><td><span class="module-badge ${stateTone(run.state)}">${esc(stateName(run.state))}</span></td></tr>`).join("");
    setPage(route, `<div class="module-grid two"><section class="module-card"><div class="module-card-head"><h2>Mission Chronicle</h2><small>${missions.length} persisted runs</small></div><div class="module-table-wrap"><table class="module-table"><thead><tr><th>Time</th><th>Target</th><th>Run</th><th>State</th></tr></thead><tbody>${history || `<tr><td colspan="4">暂无记录</td></tr>`}</tbody></table></div></section><section class="module-card"><div class="module-card-head"><h2>执行审计 / Audit</h2><small>${esc(audit.path || "")}</small></div><div class="module-card-body"><div class="audit-list">${renderAudit(audit.events || [])}</div></div></section></div>`, actionToolbar());
    bindOpenRun();
  }

  async function renderApproval() {
    const route = "/approval";
    const details = await recentDetails(40);
    const waiting = details.filter(run => run.state === "waiting_approval");
    const items = waiting.map(run => { const step = run.steps.find(item => item.state === "waiting_approval"); const evidence = run.evidence?.at(-1); return `<article class="approval-workitem"><h3>${esc(step?.tool || "Approval")} · ${esc(run.target)}</h3><p>${esc(step?.rationale || "等待人工授权")}</p><div class="fact-meta"><span class="module-badge warn">Run ${esc(short(run.id))}</span><span class="module-badge">Risk L${esc(step?.risk ?? "?")}</span><span class="module-badge">Evidence ${run.evidence?.length || 0}</span></div>${evidence ? `<pre class="terminal" style="margin-top:9px;max-height:180px"><span class="cmd">$ ${esc((evidence.argv || []).join(" "))}</span>\n${esc((evidence.stdout || "").slice(0,2500))}${evidence.stderr ? `\n<span class="stderr">${esc(evidence.stderr.slice(0,1200))}</span>` : ""}</pre>` : ""}<div class="approval-actions"><button class="danger" data-approve-run="${esc(run.id)}">✓ 批准该步骤</button><button class="ghost" data-open-run="${esc(run.id)}">查看完整任务与证据</button></div></article>`; }).join("");
    setPage(route, `<div class="module-stat-grid"><div class="module-stat"><span>Waiting</span><strong>${waiting.length}</strong></div><div class="module-stat"><span>Total inspected</span><strong>${details.length}</strong></div><div class="module-stat"><span>Grant model</span><strong>Single-use</strong></div><div class="module-stat"><span>Binding</span><strong>Tool + Target</strong></div></div><div style="height:10px"></div><section class="module-card"><div class="module-card-head"><h2>人工审批队列</h2><small>证据在批准按钮旁显示</small></div><div class="module-card-body"><div class="decision-list">${items || `<div class="module-empty"><b>目前没有候旨任务</b>验证步骤到达审批边界后会集中出现在这里。</div>`}</div></div></section>`, actionToolbar());
    bindOpenRun();
  }

  async function renderSettings() {
    const route = "/settings";
    const [settings, status] = await Promise.all([api("/api/settings"), api("/api/status")]);
    const fields = Object.entries(settings).map(([key,value]) => `<dt>${esc(key)}</dt><dd>${esc(Array.isArray(value) ? value.join(", ") : value)}</dd>`).join("");
    const checks = (status.doctor?.checks || []).map(check => `<div class="fact-item"><h3>${esc(check.name)} <span class="module-badge ${check.ok ? "ok" : "bad"}">${check.ok ? "OK" : "MISS"}</span></h3><p>${esc(check.detail)}</p></div>`).join("");
    setPage(route, `<div class="module-grid two"><section class="module-card"><div class="module-card-head"><h2>Project Configuration</h2><small>当前运行值</small></div><div class="module-card-body"><dl class="settings-grid">${fields}</dl></div></section><section class="module-card"><div class="module-card-head"><h2>Doctor / Runtime Readiness</h2><span class="module-badge ${status.doctor?.ready ? "ok" : "warn"}">${status.doctor?.ready ? "READY" : "CHECK"}</span></div><div class="module-card-body"><div class="fact-list">${checks}</div></div></section></div>`, actionToolbar(`<button class="ghost" data-route-go="/lead">查看 Lead AI</button>`));
  }

  const renderers = {"/missions":renderMissions,"/scope":renderScope,"/guard":renderGuard,"/tools":renderTools,"/intelligence":renderIntelligence,"/reasoner":renderReasoner,"/lead":renderLead,"/loop":renderLoop,"/chronicle":renderChronicle,"/approval":renderApproval,"/settings":renderSettings};

  async function renderRoute(force = false) {
    const route = normalizeRoute(location.pathname);
    pageState.route = route;
    setNav(route);
    if (route === "/") {
      overview.classList.remove("module-hidden"); root.classList.remove("active"); root.innerHTML = "";
      document.title = "雲頂天宮 | TONMEN Console";
      return;
    }
    overview.classList.add("module-hidden"); root.classList.add("active");
    document.title = `${titles[route][0]} | TONMEN Console`;
    if (!force) loading(route);
    try { await renderers[route](); document.getElementById("module-updated")?.replaceChildren(document.createTextNode(nowText())); }
    catch (error) { if (pageState.route === route) errorPage(route, error); }
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
  }

  function bindOpenRun() {
    root.querySelectorAll("[data-open-run]").forEach(button => button.addEventListener("click", () => navigate("/missions", `?run=${encodeURIComponent(button.dataset.openRun)}`)));
  }

  function bindScopeActions() {
    root.querySelector("[data-scope-form]")?.addEventListener("submit", async event => {
      event.preventDefault();
      const target = new FormData(event.currentTarget).get("target")?.toString().trim();
      if (!target) return;
      try { pageState.busy = true; await api("/api/scope/add", {method:"POST",body:{target}}); toast(`已授权: ${target}`); await renderRoute(true); }
      catch (error) { toast(error.message, true); }
      finally { pageState.busy = false; }
    });
    root.querySelectorAll("[data-scope-remove]").forEach(button => button.addEventListener("click", async () => {
      if (!confirm(`移除授权范围 ${button.dataset.scopeRemove}？`)) return;
      try { pageState.busy = true; await api("/api/scope/remove", {method:"POST",body:{target:button.dataset.scopeRemove}}); toast("Scope 已更新"); await renderRoute(true); }
      catch (error) { toast(error.message, true); }
      finally { pageState.busy = false; }
    }));
  }

  function bindCommonActions() {
    root.querySelectorAll("[data-module-refresh]").forEach(button => button.addEventListener("click", () => renderRoute(true)));
    root.querySelectorAll("[data-module-new]").forEach(button => button.addEventListener("click", () => document.getElementById("new-mission-btn")?.click()));
    root.querySelectorAll("[data-route-go]").forEach(button => button.addEventListener("click", () => navigate(button.dataset.routeGo)));
    root.querySelectorAll("[data-retry-target]").forEach(button => button.addEventListener("click", () => {
      document.getElementById("new-mission-btn")?.click();
      setTimeout(() => { const input = document.getElementById("mission-input"); if (input) input.value = button.dataset.retryTarget; }, 30);
    }));
    root.querySelectorAll("[data-resume-run]").forEach(button => button.addEventListener("click", async () => {
      try { pageState.busy = true; toast("开启新的受限天衡预算…"); await api(`/api/missions/${encodeURIComponent(button.dataset.resumeRun)}/resume`, {method:"POST",body:{}}); await renderRoute(true); toast("任务已续行"); }
      catch (error) { toast(error.message, true); }
      finally { pageState.busy = false; }
    }));
    root.querySelectorAll("[data-approve-run]").forEach(button => button.addEventListener("click", async () => {
      if (!confirm("确认批准此候旨步骤？Grant 仅绑定当前 Tool + Target，且为一次性。")) return;
      try { pageState.busy = true; toast("正在执行批准后的受治理步骤…"); await api(`/api/missions/${encodeURIComponent(button.dataset.approveRun)}/approve`, {method:"POST",body:{}}); await renderRoute(true); toast("审批已执行"); }
      catch (error) { toast(error.message, true); }
      finally { pageState.busy = false; }
    }));
    bindOpenRun();
  }

  document.addEventListener("click", event => {
    const button = event.target.closest?.(".nav-item");
    if (!button) return;
    const text = button.textContent.trim();
    const match = routeMap.find(([label]) => text.startsWith(label));
    if (!match) return;
    event.preventDefault(); event.stopImmediatePropagation();
    navigate(match[1]);
  }, true);

  window.addEventListener("popstate", () => renderRoute());
  setInterval(() => {
    if (document.hidden || pageState.busy || pageState.route === "/") return;
    renderRoute(true);
  }, 2500);

  renderRoute();
})();
