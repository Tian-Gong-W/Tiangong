(() => {
  "use strict";
  const csrfMeta = document.querySelector('meta[name="csrf-token"], meta[name="tonmen-csrf"]');
  const csrf = csrfMeta ? csrfMeta.content : "";
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];
  const state = {
    missions: [],
    current: null,
    status: null,
    scope: null,
    refreshing: false,
    polling: false,
    currentViewSignature: null,
    scopeViewSignature: null
  };
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const api = async (url, options = {}) => {
    const opts = { ...options, headers: { ...(options.headers || {}) } };
    if (opts.body && typeof opts.body !== "string") { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.body); }
    if ((opts.method || "GET") !== "GET") opts.headers["X-TONMEN-CSRF"] = csrf;
    const res = await fetch(url, opts); const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`); return data;
  };
  const toast = (message, error = false) => { const el = $("#toast"); if (!el) return; el.textContent = message; el.className = `toast show${error ? " error" : ""}`; clearTimeout(toast.t); toast.t = setTimeout(() => el.className = "toast", 3200); };
  const fmtTime = (iso) => { if (!iso) return "—"; const d = new Date(iso); return Number.isNaN(d.valueOf()) ? "—" : d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"}); };

  function missionViewSignature(m) {
    if (!m) return "none";
    return JSON.stringify({
      id: m.id,
      state: m.state,
      target: m.target,
      finished_at: m.finished_at,
      steps: (m.steps || []).map(step => [
        step.id,
        step.tool,
        step.target,
        step.state,
        step.error,
        step.evidence_id,
        step.rationale
      ]),
      evidence: (m.evidence || []).map(item => [item.id, item.tool, item.exit_code, item.finished_at]),
      observations: (m.observations || []).map(item => [item.id, item.captured_at, item.summary])
    });
  }

  // 授权目标列表：只显示干净目标名，不要符号和序号
  function renderScope() {
    const list = $("#scope-list");
    if (!list || !state.scope) return;
    const items = state.scope.allowed || [];
    const signature = JSON.stringify(items.map(item => [item.rule || "", !!item.default]));
    if (state.scopeViewSignature === signature) return;
    state.scopeViewSignature = signature;
    if (!items.length) {
      list.innerHTML = `<div class="muted">暂无授权目标</div>`;
      return;
    }
    list.innerHTML = items.map(item => {
      const rule = item.rule || "";
      const isDefault = !!item.default;
      return `<div class="scope-row">
        <span class="scope-rule" title="${esc(rule)}">${esc(rule)}</span>
        <span class="scope-badge ${isDefault ? "default" : ""}">${isDefault ? "内建" : "已授权"}</span>
        ${isDefault ? "" : `<button class="scope-remove" data-remove-scope="${esc(rule)}">移除</button>`}
      </div>`;
    }).join("");
    $$("[data-remove-scope]").forEach(btn => btn.addEventListener("click", async () => {
      try {
        state.scope = await api("/api/scope/remove", {method:"POST", body:{target: btn.dataset.removeScope}});
        state.scopeViewSignature = null;
        renderScope();
        toast(`已移除：${btn.dataset.removeScope}`);
      } catch (e) { toast(e.message, true); }
    }));
  }

  function renderChronicle(m) {
    const el = $("#chronicle-list");
    if (!el) return;
    if (!m) {
      el.innerHTML = `<div class="muted">暂无记录。任务开始后会在这里实时显示。</div>`;
      return;
    }
    const events = [];
    if (m.started_at) events.push({time: m.started_at, text: `任务开始 · ${m.target}`, tone: ""});
    (m.evidence || []).forEach(e => {
      events.push({time: e.finished_at, text: `${e.tool} 执行${e.exit_code === 0 ? "完成" : "失败"}（退出码 ${e.exit_code}）`, tone: e.exit_code === 0 ? "" : "danger"});
    });
    (m.observations || []).forEach(o => {
      events.push({time: o.captured_at, text: o.summary || "记录了一条观察", tone: ""});
    });
    const waiting = (m.steps || []).find(s => s.state === "waiting_approval");
    if (waiting) events.push({time: null, text: `需要审批 · ${waiting.tool}`, tone: "danger"});
    const failed = (m.steps || []).find(s => s.state === "failed" || s.state === "denied");
    if (failed) events.push({time: m.finished_at, text: `执行失败 · ${failed.tool}：${failed.error || "未知错误"}`, tone: "danger"});
    el.innerHTML = events.length
      ? events.map(ev => `<div class="timeline-row ${ev.tone}"><span class="timeline-time">${fmtTime(ev.time)}</span><span class="timeline-text">${esc(ev.text)}</span></div>`).join("")
      : `<div class="muted">暂无记录</div>`;
  }

  function renderApproval(m) {
    const body = $("#approval-body");
    if (!body) return;
    if (!m) {
      body.className = "approval-body idle";
      body.innerHTML = `<h3>🤖 全自主策略驱动运行中</h3><p>系统处于完全自主策略驱动运行状态，全自主调度工具链、OCR 与攻击合成。</p><button class="ghost" id="evidence-btn" disabled>查看证据链</button>`;
      return;
    }
    const failed = (m.steps || []).find(s => s.state === "failed" || s.state === "denied");
    if (failed) {
      body.className = "approval-body";
      body.innerHTML = `<h3>${esc(failed.tool)} 执行遇到阻碍</h3><p>${esc(failed.error || "工具执行未成功，正在自动重路由。")}</p><button class="ghost" id="evidence-btn" ${(m.evidence || []).length ? "" : "disabled"}>查看证据链</button><button class="primary" id="retry-btn">自动重试</button>`;
      $("#evidence-btn")?.addEventListener("click", showEvidence);
      $("#retry-btn")?.addEventListener("click", () => openMissionDialog(m.target));
    } else {
      body.className = "approval-body idle";
      body.innerHTML = `<h3>🤖 全自主策略驱动推理中</h3><p>状态：<strong>${esc(m.state)}</strong>。全程策略驱动自主决策与越权验证。</p><button class="ghost" id="evidence-btn" ${(m.evidence || []).length ? "" : "disabled"}>查看证据链</button>`;
      $("#evidence-btn")?.addEventListener("click", showEvidence);
    }
  }

  function updateDeck(m) {
    const current = $("#deck-current");
    if (current) current.textContent = m ? `${m.target}（${m.state} · 100% 自主运行）` : "尚无任务";
    const evidenceBtn = $("#deck-evidence");
    if (evidenceBtn) evidenceBtn.disabled = !(m && (m.evidence || []).length);
  }

  function renderMissionIfChanged(loaded) {
    const signature = missionViewSignature(loaded);
    state.current = loaded;
    if (state.currentViewSignature === signature) return false;
    state.currentViewSignature = signature;
    renderApproval(loaded);
    renderChronicle(loaded);
    updateDeck(loaded);
    return true;
  }

  async function loadMission(id) {
    if (!id) {
      state.current = null;
      if (state.currentViewSignature === "none") return;
      state.currentViewSignature = "none";
      renderApproval(null);
      renderChronicle(null);
      updateDeck(null);
      return;
    }
    try {
      const loaded = await api(`/api/missions/${encodeURIComponent(id)}`);
      renderMissionIfChanged(loaded);
    } catch (e) {
      state.current = null;
      state.currentViewSignature = null;
      renderApproval(null);
      renderChronicle(null);
      updateDeck(null);
      toast(`加载任务失败：${e.message}`, true);
    }
  }

  async function refreshAll(preferredId = null) {
    if (state.refreshing) return;
    state.refreshing = true;
    try {
      const [status, scope, ms] = await Promise.all([
        api("/api/status").catch(() => null),
        api("/api/scope"),
        api("/api/missions")
      ]);
      state.status = status;
      state.scope = scope;
      state.missions = ms.missions || [];
      renderScope();
      const id = preferredId || state.current?.id || state.missions[0]?.id || null;
      await loadMission(id);

      // 健康状态
      const health = $("#health-pill");
      if (health && status?.doctor) {
        const ready = status.doctor.ready;
        const strong = health.querySelector("strong");
        if (strong) {
          strong.textContent = ready ? "良好" : "需检查";
          strong.style.color = ready ? "var(--green)" : "var(--amber)";
        }
      }
    } catch (e) {
      toast(e.message, true);
    } finally {
      state.refreshing = false;
    }
  }

  async function approveCurrent() {
    if (!state.current) return;
    if (!confirm("确认批准当前等待的步骤？批准仅绑定当前工具和目标，且为一次性。")) return;
    try {
      toast("正在批准并继续执行…");
      const accepted = await api(`/api/missions/${state.current.id}/approve`, {method:"POST", body:{}});
      if (accepted?.id) renderMissionIfChanged(accepted);
      await refreshAll(state.current?.id);
      toast("批准已完成，任务状态已更新。");
    } catch (e) { toast(e.message, true); }
  }

  async function resumeCurrent() {
    if (!state.current) return;
    try {
      toast("正在续行…");
      const resumed = await api(`/api/missions/${state.current.id}/resume`, {method:"POST", body:{}});
      if (resumed?.id) renderMissionIfChanged(resumed);
      await refreshAll(state.current?.id);
      toast("任务已续行。");
    } catch (e) { toast(e.message, true); }
  }

  function showEvidence() {
    const m = state.current;
    if (!m || !(m.evidence || []).length) {
      toast("此任务没有可用的原始证据。", true);
      return;
    }
    const dialog = $("#evidence-dialog");
    const tabs = $("#evidence-tabs");
    const pre = $("#evidence-content");
    if (!dialog || !tabs || !pre) return;
    tabs.innerHTML = m.evidence.map((e, i) => `<button data-ev="${i}">${esc(e.tool)} · 退出码 ${e.exit_code}</button>`).join("");
    const show = (i) => {
      const e = m.evidence[i];
      pre.textContent = `$ ${(e.argv || []).join(" ")}\n退出码: ${e.exit_code}\n\n--- 标准输出 ---\n${e.stdout || "(空)"}\n\n--- 错误输出 ---\n${e.stderr || "(空)"}`;
    };
    $$("[data-ev]").forEach(b => b.addEventListener("click", () => show(Number(b.dataset.ev))));
    show(m.evidence.length - 1);
    dialog.showModal();
  }

  function openMissionDialog(target = "") {
    const input = $("#mission-input");
    const dialog = $("#mission-dialog");
    if (input) input.value = target || "";
    if (dialog) {
      dialog.showModal();
      setTimeout(() => input?.focus(), 30);
    }
  }

  // 选项卡切换逻辑
  $$(".nav-item").forEach(item => {
    item.addEventListener("click", e => {
      const tabId = item.getAttribute("data-tab");
      if (!tabId) return;
      e.preventDefault();
      $$(".nav-item").forEach(n => n.classList.remove("active"));
      item.classList.add("active");
      $$(".tab-pane").forEach(p => {
        p.style.display = "none";
        p.classList.remove("active");
      });
      const targetPane = $(`#${tabId}`);
      if (targetPane) {
        targetPane.style.display = "block";
        targetPane.classList.add("active");
      }
      // 按需加载模块数据
      if (tabId === "verification") loadVerificationModule();
      if (tabId === "credentials") loadCredentialsModule();
      if (tabId === "infra") loadInfraModule();
      if (tabId === "skirmish") loadSkirmishModule();
      if (tabId === "expansion") loadExpansionModule();
      if (tabId === "llm") loadLlmModule();
      if (tabId === "cairn") loadCairnModule();
      if (tabId === "arena") loadArenaModule();
      if (tabId === "skills-arsenal") loadSkillsArsenalModule();
      if (tabId === "cascade") loadCascadeModule();
      if (tabId === "evolution") loadEvolutionModule();
      if (tabId === "missions") loadMissionsModule();
      if (tabId === "injection") loadInjectionModule();
    });
  });

  async function loadInjectionModule() {
    const promptSelect = $("#injection-prompt-select");
    const targetSelect = $("#injection-target-select");
    const textarea = $("#injection-content-textarea");
    const historyList = $("#injection-history-list");
    const dispatchBtn = $("#dispatch-injection-btn");
    if (!promptSelect || !historyList) return;

    try {
      const data = await api("/api/injection");
      const inj = data.injection || {};
      const templates = inj.templates || [];
      const history = inj.history || [];

      promptSelect.innerHTML = templates.map(t => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join("");
      
      const updateTextarea = () => {
        const selectedId = promptSelect.value;
        const t = templates.find(x => x.id === selectedId);
        if (t && textarea) textarea.value = t.content;
      };

      promptSelect.onchange = updateTextarea;
      updateTextarea();

      historyList.innerHTML = history.length ? history.map(h => `
        <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.75rem; font-size: 0.85rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
            <strong>[${esc(h.timestamp)}] 投递至: ${esc(h.target)}</strong>
            <span style="font-size: 0.75rem; color: #0369a1; background: #e0f2fe; padding: 0.1rem 0.4rem; border-radius: 4px;">${esc(h.template_name)}</span>
          </div>
          <div style="font-family: monospace; color: #334155; background: #f1f5f9; padding: 0.3rem 0.5rem; border-radius: 4px; margin-bottom: 0.3rem; white-space: pre-wrap; word-break: break-all;">${esc(h.content)}</div>
          <div style="font-size: 0.78rem; color: #059669;">状态: ${esc(h.status)}</div>
        </div>
      `).join("") : `<div class="muted">暂无下发记录</div>`;

      dispatchBtn.onclick = async () => {
        const template_id = promptSelect.value;
        const target = targetSelect.value;
        const content = textarea.value;
        try {
          const res = await api("/api/injection/dispatch", {
            method: "POST",
            body: { template_id, target, content }
          });
          toast("成功下发注入提示内容并执行沙箱对抗！");
          loadInjectionModule();
        } catch (err) {
          toast(err.message || String(err), true);
        }
      };
    } catch (e) {
      historyList.innerHTML = `<div class="muted">加载注入控制台失败：${esc(e.message)}</div>`;
    }
  }

  function renderD3EvolutionTree(containerId, item) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";

    const width = container.clientWidth || 580;
    const height = 180;

    const treeData = {
      name: "初始漏洞假设 (Initial Hypothesis)",
      type: "Hypothesis",
      detail: item.title,
      children: [
        {
          name: "多 LLM 委员会策略推演",
          type: "Inference",
          detail: "Claude / GPT 攻击面与路径推演",
          children: [
            {
              name: "五要素载荷与探针构造",
              type: "Payload",
              detail: item.five_elements?.payload ? item.five_elements.payload.split('\n')[0].slice(0, 35) + "..." : "Payload test",
              children: [
                {
                  name: item.type === "Fact" ? "确认事实 (Verified Fact)" : "实验测试中 (Testing)",
                  type: item.type,
                  detail: `${item.status} (${item.target})`
                }
              ]
            }
          ]
        }
      ]
    };

    if (typeof d3 === "undefined") {
      container.innerHTML = `<div style="padding:10px; color:#f87171;">D3.js 未加载</div>`;
      return;
    }

    const svg = d3.select(container)
      .append("svg")
      .attr("width", "100%")
      .attr("height", height)
      .attr("viewBox", `0 0 ${width} ${height}`)
      .style("background", "#0f172a")
      .style("border-radius", "8px");

    const g = svg.append("g").attr("transform", "translate(40, 20)");

    const root = d3.hierarchy(treeData);
    const treeLayout = d3.tree().size([height - 40, width - 180]);
    treeLayout(root);

    g.selectAll(".link")
      .data(root.links())
      .enter()
      .append("path")
      .attr("class", "link")
      .attr("fill", "none")
      .attr("stroke", "#38bdf8")
      .attr("stroke-width", 1.5)
      .attr("opacity", 0.6)
      .attr("d", d3.linkHorizontal()
        .x(d => d.y)
        .y(d => d.x)
      );

    const node = g.selectAll(".node")
      .data(root.descendants())
      .enter()
      .append("g")
      .attr("class", "node")
      .attr("transform", d => `translate(${d.y},${d.x})`);

    node.append("circle")
      .attr("r", 6)
      .attr("fill", d => d.data.type === "Fact" ? "#22c55e" : d.data.type === "Payload" ? "#eab308" : "#38bdf8")
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 2);

    node.append("text")
      .attr("dy", "0.31em")
      .attr("dx", d => d.children ? -10 : 10)
      .attr("text-anchor", d => d.children ? "end" : "start")
      .text(d => d.data.name)
      .style("fill", "#f8fafc")
      .style("font-size", "11px")
      .style("font-family", "sans-serif")
      .style("font-weight", "600");

    node.append("text")
      .attr("dy", "1.4em")
      .attr("dx", d => d.children ? -10 : 10)
      .attr("text-anchor", d => d.children ? "end" : "start")
      .text(d => d.data.detail)
      .style("fill", "#94a3b8")
      .style("font-size", "9px")
      .style("font-family", "sans-serif");
  }

  async function loadVerificationModule() {
    const list = $("#verification-list");
    if (!list) return;
    try {
      const data = await api("/api/verification");
      const items = data.items || [];
      if (!items.length) {
        list.innerHTML = `<div class="muted">暂无验证项目</div>`;
        return;
      }
      list.innerHTML = items.map(item => `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <div><strong style="font-size: 1.05rem; color: #0f172a;">${esc(item.title)}</strong> <span style="font-size: 0.85rem; color: #64748b; margin-left: 0.5rem;">${esc(item.target)}</span></div>
            <span style="padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; background: ${item.type === 'Fact' ? '#dcfce7; color: #166534;' : '#fef9c3; color: #854d0e;'}">${esc(item.type)} · ${esc(item.status)}</span>
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; font-size: 0.88rem; margin-top: 0.75rem;">
            <div style="background: #fff; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px;">
              <strong>Payload (攻击载荷):</strong>
              <pre style="margin-top: 0.25rem; background: #0f172a; color: #e2e8f0; padding: 0.5rem; border-radius: 4px; overflow-x: auto; font-size: 0.8rem;">${esc(item.five_elements.payload)}</pre>
            </div>
            <div style="background: #fff; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px;">
              <strong>Response (响应特征):</strong>
              <pre style="margin-top: 0.25rem; background: #0f172a; color: #e2e8f0; padding: 0.5rem; border-radius: 4px; overflow-x: auto; font-size: 0.8rem;">${esc(item.five_elements.response)}</pre>
            </div>
            <div style="background: #fff; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px;">
              <strong>Trace (执行链路):</strong>
              <div style="margin-top: 0.25rem; color: #334155;">${esc(item.five_elements.trace)}</div>
            </div>
            <div style="background: #fff; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px;">
              <strong>Impact (影响评估):</strong>
              <div style="margin-top: 0.25rem; color: #dc2626; font-weight: 500;">${esc(item.five_elements.impact)}</div>
            </div>
          </div>
          <div style="margin-top: 0.75rem; background: #1e293b; color: #f8fafc; padding: 0.75rem; border-radius: 8px; font-size: 0.85rem;">
            <strong>Reproducibility (可复现性 PoC):</strong>
            <div style="font-family: monospace; color: #38bdf8; margin-top: 0.25rem;">${esc(item.five_elements.reproducibility)}</div>
          </div>
          <div style="margin-top: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
            <button class="ghost small" data-toggle-tree="${esc(item.id)}" style="background: #e0f2fe; color: #0369a1; border-color: #bae6fd;">📊 展开/收起 D3 演变关联推演树 (Evolution Tree)</button>
            <span style="font-size: 0.75rem; color: #64748b;">ID: ${esc(item.id)}</span>
          </div>
          <div id="d3-tree-wrap-${esc(item.id)}" style="display: none; margin-top: 0.75rem;"></div>
        </div>
      `).join("");

      list.querySelectorAll("[data-toggle-tree]").forEach(btn => {
        const id = btn.dataset.toggleTree;
        const wrap = document.getElementById(`d3-tree-wrap-${id}`);
        btn.addEventListener("click", () => {
          const isHidden = wrap.style.display === "none";
          wrap.style.display = isHidden ? "block" : "none";
          btn.textContent = isHidden ? "📊 收起 D3 关联推演树" : "📊 展开/收起 D3 演变关联推演树 (Evolution Tree)";
          if (isHidden) {
            const item = items.find(i => i.id === id);
            if (item) renderD3EvolutionTree(`d3-tree-wrap-${id}`, item);
          }
        });
      });
    } catch (e) {
      list.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  async function loadCredentialsModule() {
    const list = $("#credentials-list");
    if (!list) return;
    try {
      const data = await api("/api/credentials");
      const creds = data.credentials || [];
      list.innerHTML = `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
          <h3 style="margin-bottom: 0.5rem; font-size: 1.1rem; color: #0f172a;">Token / Session 自动续期与持久化池</h3>
          <p style="color: #64748b; font-size: 0.9rem; margin-bottom: 1rem;">系统持续监控凭据有效期，失效时自动通过绕过或重新认证恢复状态。</p>
          <div style="display: flex; flex-direction: column; gap: 0.75rem;">
            ${creds.map(c => `
              <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                  <strong style="color: #0f172a; font-size: 1rem;">${esc(c.username)}</strong>
                  <span style="background: #e0f2fe; color: #0369a1; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;">${esc(c.role)}</span>
                  <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.25rem;">凭据类型：${esc(c.token_type)} (${esc(c.token_preview)}) | 有效期剩余：${c.expires_in_sec}秒</div>
                  <div style="font-size: 0.85rem; color: #0f766e; margin-top: 0.25rem;">关联资产：${(c.associated_assets || []).join(", ")}</div>
                </div>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                  <span style="color: #16a34a; font-weight: 600; font-size: 0.85rem;">● ${esc(c.status)}</span>
                  <button class="ghost small" onclick="alert('已手动触发该凭据的自动续期探针。')">立即续期</button>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    } catch (e) {
      list.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  async function loadInfraModule() {
    const box = $("#infra-content");
    if (!box) return;
    try {
      const data = await api("/api/infra");
      const inf = data.infrastructure || {};
      const proxies = inf.proxies || [];
      const fp = inf.fingerprints || {};
      box.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.25rem;">
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <h3 style="margin-bottom: 0.75rem; font-size: 1.05rem; color: #0f172a;">多层级代理池状态</h3>
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
              ${proxies.map(p => `
                <div style="background: #fff; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px;">
                  <div style="display: flex; justify-content: space-between;"><strong style="color: #0f172a;">${esc(p.type)}</strong><span style="color: #16a34a; font-size: 0.8rem;">${esc(p.status)}</span></div>
                  <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.25rem;">池名称：${esc(p.pool)}</div>
                  <div style="font-size: 0.85rem; color: #475569; margin-top: 0.15rem;">可用节点：${p.active_nodes} 个 | 平均延迟：${p.latency}</div>
                </div>
              `).join("")}
            </div>
          </div>
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <h3 style="margin-bottom: 0.75rem; font-size: 1.05rem; color: #0f172a;">动态指纹混淆池</h3>
            <div style="font-size: 0.9rem; color: #334155; display: flex; flex-direction: column; gap: 0.75rem;">
              <div style="background: #fff; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px;">
                <strong>User-Agent 轮换池：</strong>
                <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.25rem;">${(fp.user_agents || []).join("<br>")}</div>
              </div>
              <div style="background: #fff; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px;">
                <strong>TLS 指纹 (JA3/JA4)：</strong>
                <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.25rem;">${(fp.tls_profiles || []).join("<br>")}</div>
              </div>
              <div style="background: #fff; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px;">
                <strong>Canvas 噪声与 WebRTC 动态防追踪：</strong>
                <div style="font-size: 0.8rem; color: #16a34a; margin-top: 0.25rem;">熵源：${esc(fp.canvas_noise)} | WebRTC 混淆：${esc(fp.webrtc_spoof)}</div>
              </div>
            </div>
          </div>
        </div>
      `;
    } catch (e) {
      box.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  async function loadSkirmishModule() {
    const box = $("#skirmish-content");
    if (!box) return;
    try {
      const data = await api("/api/skirmish");
      const sk = data.skirmish || {};
      const agents = sk.agents || [];
      box.innerHTML = `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; gap: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
            <div><strong style="font-size: 1.1rem; color: #0f172a;">当前博弈轮次：第 ${sk.round} 轮 / 共 ${sk.max_rounds} 轮</strong></div>
            <div style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600;">生存 TTL 倒计时：${sk.ttl_seconds_left} 秒</div>
          </div>
          <div style="background: #e2e8f0; padding: 0.75rem; border-radius: 8px; font-size: 0.9rem; color: #1e293b;">
            <strong>最近演化事件：</strong> ${esc(sk.recent_event)}
          </div>
          <div id="skirmish-recharts-root"></div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem;">
            ${agents.map(a => `
              <div style="background: #fff; border: 2px solid ${a.status === 'Leading' ? '#22c55e' : '#cbd5e1'}; border-radius: 10px; padding: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                  <strong style="color: #0f172a;">${esc(a.name)}</strong>
                  <span style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: ${a.status === 'Leading' ? '#dcfce7; color: #166534;' : '#f1f5f9; color: #475569;'}; border-radius: 4px;">${esc(a.status)}</span>
                </div>
                <div style="font-size: 0.85rem; color: #64748b;">擅长领域：${esc(a.specialty)}</div>
                <div style="margin-top: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 1.1rem; font-weight: 700; color: #0284c7;">积分：${a.score} pts</span>
                  <span style="font-size: 0.85rem; font-weight: 600; color: #0f172a;">子代理数：${a.sub_agents} 个</span>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
      renderSkirmishChart(sk);
    } catch (e) {
      box.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  function renderSkirmishChart(sk) {
    const containerId = "skirmish-recharts-root";
    setTimeout(() => {
      const rootEl = document.getElementById(containerId);
      if (!rootEl || !window.React || !window.ReactDOM || !window.Recharts) return;

      const { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } = window.Recharts;
      const { createElement: h, useState } = window.React;

      function ChartWidget() {
        const [metric, setMetric] = useState('score'); // 'score', 'accuracy', 'success', 'risk'

        const currentRound = sk.round || 7;
        const data = [];
        for (let r = Math.max(1, currentRound - 8); r <= currentRound; r++) {
          data.push({
            round: `第 ${r} 轮`,
            alpha: Math.round(1000 + (sk.agents[0]?.score - 1000 || 420) * (r / currentRound)),
            beta: Math.round(900 + (sk.agents[1]?.score - 900 || 380) * (r / currentRound)),
            gamma: Math.round(700 + (sk.agents[2]?.score - 700 || 250) * (r / currentRound)),
            alphaAcc: Math.min(98, Math.round(85 + 13 * Math.sin(r))),
            betaAcc: Math.min(95, Math.round(80 + 15 * Math.cos(r))),
            gammaAcc: Math.min(90, Math.round(75 + 12 * Math.sin(r + 1))),
            alphaSucc: Math.min(96, Math.round(82 + 14 * Math.cos(r * 0.5))),
            betaSucc: Math.min(92, Math.round(78 + 14 * Math.sin(r * 0.5))),
            gammaSucc: Math.min(88, Math.round(70 + 15 * Math.cos(r))),
            alphaRisk: Math.min(99, Math.round(90 + 9 * Math.sin(r * 0.8))),
            betaRisk: Math.min(94, Math.round(85 + 9 * Math.cos(r * 0.8))),
            gammaRisk: Math.min(89, Math.round(80 + 9 * Math.sin(r))),
          });
        }

        const linesConfig = metric === 'score' ? [
          { key: 'alpha', name: 'Strategist Alpha (积分)', stroke: '#0284c7' },
          { key: 'beta', name: 'Strategist Beta (积分)', stroke: '#7c3aed' },
          { key: 'gamma', name: 'Strategist Gamma (积分)', stroke: '#d97706' },
        ] : metric === 'accuracy' ? [
          { key: 'alphaAcc', name: 'Alpha 准确度 (%)', stroke: '#0284c7' },
          { key: 'betaAcc', name: 'Beta 准确度 (%)', stroke: '#7c3aed' },
          { key: 'gammaAcc', name: 'Gamma 准确度 (%)', stroke: '#d97706' },
        ] : metric === 'success' ? [
          { key: 'alphaSucc', name: 'Alpha 成功率 (%)', stroke: '#0284c7' },
          { key: 'betaSucc', name: 'Beta 成功率 (%)', stroke: '#7c3aed' },
          { key: 'gammaSucc', name: 'Gamma 成功率 (%)', stroke: '#d97706' },
        ] : [
          { key: 'alphaRisk', name: 'Alpha 风险控制 (%)', stroke: '#0284c7' },
          { key: 'betaRisk', name: 'Beta 风险控制 (%)', stroke: '#7c3aed' },
          { key: 'gammaRisk', name: 'Gamma 风险控制 (%)', stroke: '#d97706' },
        ];

        return h('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.75rem' } }, [
          h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' } }, [
            h('strong', { style: { fontSize: '1.05rem', color: '#0f172a' } }, '📊 数字角斗场实时对抗走势图 (Recharts)'),
            h('div', { style: { display: 'flex', gap: '0.4rem', flexWrap: 'wrap' } }, [
              h('button', { 
                type: 'button',
                onClick: () => setMetric('score'), 
                className: metric === 'score' ? 'primary small' : 'ghost small',
                style: { fontSize: '0.8rem', padding: '0.25rem 0.6rem' }
              }, '综合积分'),
              h('button', { 
                type: 'button',
                onClick: () => setMetric('accuracy'), 
                className: metric === 'accuracy' ? 'primary small' : 'ghost small',
                style: { fontSize: '0.8rem', padding: '0.25rem 0.6rem' }
              }, '准确度'),
              h('button', { 
                type: 'button',
                onClick: () => setMetric('success'), 
                className: metric === 'success' ? 'primary small' : 'ghost small',
                style: { fontSize: '0.8rem', padding: '0.25rem 0.6rem' }
              }, '成功率'),
              h('button', { 
                type: 'button',
                onClick: () => setMetric('risk'), 
                className: metric === 'risk' ? 'primary small' : 'ghost small',
                style: { fontSize: '0.8rem', padding: '0.25rem 0.6rem' }
              }, '风险控制'),
            ])
          ]),
          h('div', { style: { width: '100%', height: '300px', background: '#fff', borderRadius: '8px', padding: '1rem', border: '1px solid #e2e8f0' } },
            h(ResponsiveContainer, { width: '100%', height: '100%' },
              h(LineChart, { data }, [
                h(CartesianGrid, { strokeDasharray: '3 3', stroke: '#f1f5f9' }),
                h(XAxis, { dataKey: 'round', stroke: '#64748b', fontSize: 12 }),
                h(YAxis, { stroke: '#64748b', fontSize: 12 }),
                h(Tooltip, { contentStyle: { background: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff', fontSize: '12px' } }),
                h(Legend, { wrapperStyle: { fontSize: '12px', paddingTop: '8px' } }),
                ...linesConfig.map(l => h(Line, { 
                  key: l.key, 
                  type: 'monotone', 
                  dataKey: l.key, 
                  name: l.name, 
                  stroke: l.stroke, 
                  strokeWidth: 3, 
                  dot: { r: 4 }, 
                  activeDot: { r: 6 } 
                }))
              ])
            )
          )
        ]);
      }

      if (!window._skirmishReactRoot) {
        window._skirmishReactRoot = window.ReactDOM.createRoot(rootEl);
      }
      window._skirmishReactRoot.render(h(ChartWidget));
    }, 50);
  }

  $("#skirmish-tick-btn")?.addEventListener("click", async () => {
    try {
      toast("正在推进多 LLM 博弈轮次与子代理掠夺模拟…");
      await api("/api/skirmish/tick", {method:"POST", body:{}});
      await loadSkirmishModule();
      toast("博弈轮次已更新！");
    } catch (e) { toast(e.message, true); }
  });

  async function loadExpansionModule() {
    const box = $("#expansion-content");
    if (!box) return;
    try {
      const data = await api("/api/expansion");
      const exp = data.expansion || {};
      const nodes = exp.nodes || [];
      box.innerHTML = `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
          <h3 style="margin-bottom: 0.5rem; font-size: 1.1rem; color: #0f172a;">主域名：${esc(exp.primary_domain)} 的生态关联图谱</h3>
          <p style="color: #64748b; font-size: 0.9rem; margin-bottom: 1rem;">通过关联度评分（Target Affinity）自动跨越硬边界，将关联 API 与三方服务纳入攻击范围。</p>
          <div style="display: flex; flex-direction: column; gap: 0.75rem;">
            ${nodes.map(n => `
              <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                  <strong style="color: #0f172a; font-size: 1.05rem;">${esc(n.name)}</strong>
                  <span style="background: #e0f2fe; color: #0369a1; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;">${esc(n.type)}</span>
                  <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.25rem;">状态：${esc(n.status)}</div>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem;">
                  <div style="text-align: right;">
                    <div style="font-size: 0.75rem; color: #64748b;">亲和度评分</div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: ${n.affinity > 90 ? '#dc2626' : n.affinity > 75 ? '#d97706' : '#16a34a'};">${n.affinity}%</div>
                  </div>
                  <button class="primary small" onclick="alert('已将 ${esc(n.name)} 纳入动态授权边界与深度渗透测试队列。')">发起扩张渗透</button>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    } catch (e) {
      box.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  async function loadCascadeModule() {
    const box = $("#cascade-content");
    if (!box) return;
    try {
      const data = await api("/api/cascade");
      const combos = data.combinations || [];
      box.innerHTML = `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
          <h3 style="margin-bottom: 0.5rem; font-size: 1.1rem; color: #0f172a;">风险组合算子与系统性级联失效模拟</h3>
          <p style="color: #64748b; font-size: 0.9rem; margin-bottom: 1rem;">计算低风险点之间的耦合系数（Coupling Coefficient），自动生成复合攻击意图并触发连锁反应。</p>
          <div style="display: flex; flex-direction: column; gap: 1rem;">
            ${combos.map(c => `
              <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                  <strong style="color: #0f172a; font-size: 1.05rem;">${esc(c.composite_intention)}</strong>
                  <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.25rem;">风险点 A：${esc(c.point_a)}</div>
                  <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.15rem;">风险点 B：${esc(c.point_b)}</div>
                  <div style="font-size: 0.85rem; color: #0f766e; margin-top: 0.25rem;">状态：${esc(c.status)}</div>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem;">
                  <div style="text-align: right;">
                    <div style="font-size: 0.75rem; color: #64748b;">耦合系数</div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: #dc2626;">${c.coupling_coefficient * 100}%</div>
                  </div>
                  <button class="primary small" onclick="triggerCascade('${c.id}')">触发连锁仿真</button>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    } catch (e) {
      box.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  window.triggerCascade = async function(id) {
    try {
      toast("正在执行组合风险算子与连锁级联仿真...");
      await api("/api/cascade/simulate", { method: "POST", body: { id } });
      await loadCascadeModule();
      toast("连锁反应仿真已完成！");
    } catch (e) { toast(e.message, true); }
  };

  async function loadEvolutionModule() {
    const box = $("#evolution-content");
    if (!box) return;
    try {
      const data = await api("/api/evolution");
      const ev = data.evolution || {};
      const fails = ev.failure_records || [];
      const history = ev.reroute_history || [];
      box.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.25rem;">
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <h3 style="margin-bottom: 0.75rem; font-size: 1.05rem; color: #0f172a;">失败分析与路径重构器</h3>
            <div style="margin-bottom: 1rem; background: #e0f2fe; color: #0369a1; padding: 0.75rem; border-radius: 8px; font-size: 0.9rem;">
              <strong>当前演化策略：</strong> ${esc(ev.current_strategy)}
            </div>
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;">
              <button class="primary small" onclick="triggerReroute('lateral')">横向转向 (Protocol Shift)</button>
              <button class="primary small" onclick="triggerReroute('depth')">深度转向 (WAF Bypass)</button>
              <button class="primary small" onclick="triggerReroute('breadth')">广度转向 (Asset Graph Branch)</button>
            </div>
            <h4 style="font-size: 0.95rem; margin-bottom: 0.5rem; color: #1e293b;">路径重构历史事件：</h4>
            <ul style="padding-left: 1.2rem; font-size: 0.85rem; color: #475569; display: flex; flex-direction: column; gap: 0.3rem;">
              ${history.map(h => `<li>${esc(h)}</li>`).join("")}
            </ul>
          </div>
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <h3 style="margin-bottom: 0.75rem; font-size: 1.05rem; color: #0f172a;">历史阻断与失败分析记录</h3>
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
              ${fails.map(f => `
                <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.75rem;">
                  <strong style="color: #dc2626; font-size: 0.9rem;">${esc(f.path)}</strong>
                  <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.2rem;">阻断原因：${esc(f.cause)}</div>
                  <div style="font-size: 0.8rem; color: #16a34a; margin-top: 0.2rem;">应对动作：${esc(f.action_taken)}</div>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      `;
    } catch (e) {
      box.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  window.triggerReroute = async function(direction) {
    try {
      toast("正在执行决策反馈路径重构...");
      await api("/api/evolution/reroute", { method: "POST", body: { direction } });
      await loadEvolutionModule();
      toast("路径重构成功！");
    } catch (e) { toast(e.message, true); }
  };

  async function loadMissionsModule() {
    const list = $("#missions-list-view");
    if (!list) return;
    try {
      const data = await api("/api/missions");
      const ms = data.missions || [];
      if (!ms.length) {
        list.innerHTML = `<div class="muted">暂无任务记录</div>`;
        return;
      }
      list.innerHTML = ms.map(m => `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong>${esc(m.target)}</strong> <span style="font-size: 0.8rem; color: #64748b; margin-left: 0.5rem;">ID: ${esc(m.id)}</span>
            <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.25rem;">状态：${esc(m.state)} | 开始时间：${fmtTime(m.started_at)}</div>
          </div>
          <button class="ghost small" onclick="loadMission('${esc(m.id)}'); document.querySelector('[data-tab=overview]').click();">查看详情</button>
        </div>
      `).join("");
    } catch (e) {
      list.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  $("#deck-refresh")?.addEventListener("click", () => refreshAll(state.current?.id));
  $("#deck-approve")?.addEventListener("click", approveCurrent);
  $("#deck-evidence")?.addEventListener("click", showEvidence);
  $("#deck-resume")?.addEventListener("click", resumeCurrent);

  $$(".close-dialog").forEach(b => b.addEventListener("click", () => $("#mission-dialog")?.close()));
  $$(".close-evidence").forEach(b => b.addEventListener("click", () => $("#evidence-dialog")?.close()));

  $("#mission-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const target = $("#mission-input")?.value.trim();
    if (!target) return;
    try {
      $("#mission-dialog")?.close();
      toast(`正在执行任务：${target}`);
      const m = await api("/api/missions/start", {
        method: "POST",
        body: {
          target,
          max_iterations: Number($("#max-iterations")?.value || 8),
          max_executions: Number($("#max-executions")?.value || 3),
          max_duration_seconds: Number($("#max-duration")?.value || 300),
          max_repeat_decisions: 2
        }
      });
      renderMissionIfChanged(m);
      await refreshAll(m.id);
      toast(m.state === "failed" ? "任务执行失败，请查看证据。" : "任务已启动。", m.state === "failed");
    } catch (err) { toast(err.message, true); }
  });

  // 总览里的授权表单
  $("#scope-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const input = $("#scope-input");
    const target = input?.value.trim();
    if (!target) return;
    try {
      state.scope = await api("/api/scope/add", {method:"POST", body:{target}});
      state.scopeViewSignature = null;
      if (input) input.value = "";
      renderScope();
      toast(`已加入授权：${target}`);
    } catch (err) { toast(err.message, true); }
  });

  // 主操作台的授权表单
  $("#deck-scope-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const input = $("#deck-scope-input");
    const target = input?.value.trim();
    if (!target) return;
    try {
      state.scope = await api("/api/scope/add", {method:"POST", body:{target}});
      state.scopeViewSignature = null;
      if (input) input.value = "";
      renderScope();
      toast(`已加入授权：${target}`);
    } catch (err) { toast(err.message, true); }
  });

  refreshAll();
  setInterval(async () => {
    if (document.hidden || state.polling) return;
    state.polling = true;
    try {
      const ms = await api("/api/missions");
      state.missions = ms.missions || [];
      if (state.current) await loadMission(state.current.id);
      else if (state.missions[0]) await loadMission(state.missions[0].id);
    } catch (_) {
      // Polling is supplemental; the event stream and manual refresh remain active.
    } finally {
      state.polling = false;
    }
  }, 15000);

  // LLM Configurations & Failover Chain
  async function loadLlmModule() {
    const box = $("#llm-content");
    if (!box) return;
    try {
      const data = await api("/api/llm/configs");
      const configs = data.configs || [];
      box.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 1rem;">
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <div>
                <strong style="font-size: 1.1rem; color: #0f172a;">厂商解耦的多模型路由与故障转移池</strong>
                <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.2rem;">支持 Anthropic、OpenAI、OpenAI Responses 格式。星标 (★) 代表当前激活配置，故障转移链按 priority 自动轮换。</div>
              </div>
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.85rem; margin-top: 1rem;">
              ${configs.map(c => `
                <div style="background: #fff; border: 2px solid ${c.is_default ? '#22c55e' : '#cbd5e1'}; border-radius: 10px; padding: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                  <div>
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                      <span style="font-size: 1.2rem; cursor: pointer;" title="${c.is_default ? '当前默认激活' : '设为激活'}" onclick="activateLlm('${c.id}')">${c.is_default ? '★' : '☆'}</span>
                      <strong style="color: #0f172a; font-size: 1.05rem;">${esc(c.name)}</strong>
                      <span style="background: #e0f2fe; color: #0369a1; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">${esc(c.format)}</span>
                      <span style="background: #f1f5f9; color: #475569; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">模型: ${esc(c.model)}</span>
                      ${c.pool_exclude ? '<span style="background: #fee2e2; color: #991b1b; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">不参与轮询</span>' : ''}
                    </div>
                    <div style="font-size: 0.85rem; color: #64748b; display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.3rem;">
                      <span>Base URL: ${esc(c.base_url || '默认')}</span>
                      <span>代理: ${esc(c.proxy || '直连')}</span>
                      <span>Key 状态: <code style="color: #0f766e;">${esc(c.api_key)}</code></span>
                      <span>限速: ${c.rate_per_second || 0} req/s, ${c.rate_per_minute || 0} req/m</span>
                      <span>上下文: ${c.context_window_k}K</span>
                      <span>优先级: P${c.priority}</span>
                    </div>
                  </div>
                  <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <button class="ghost small" onclick="editLlm('${c.id}')">编辑</button>
                    <button class="ghost small" style="color: #dc2626;" onclick="deleteLlm('${c.id}')">删除</button>
                  </div>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      `;
    } catch (e) {
      box.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  $("#llm-new-btn")?.addEventListener("click", () => {
    const idField = $("#llm-id");
    const nameField = $("#llm-name");
    const formatField = $("#llm-format");
    const modelField = $("#llm-model");
    const baseUrlField = $("#llm-base-url");
    const proxyField = $("#llm-proxy");
    const apiKeyField = $("#llm-api-key");
    const rateSecField = $("#llm-rate-sec");
    const rateMinField = $("#llm-rate-min");
    const contextKField = $("#llm-context-k");
    const priorityField = $("#llm-priority");
    const maxTokensField = $("#llm-max-tokens");
    const thinkingField = $("#llm-thinking");
    const effortField = $("#llm-effort");
    const streamingField = $("#llm-streaming");
    const excludeField = $("#llm-exclude");

    if (idField) idField.value = "";
    if (nameField) nameField.value = "";
    if (formatField) formatField.value = "anthropic";
    if (modelField) modelField.value = "claude-opus-4-8";
    if (baseUrlField) baseUrlField.value = "";
    if (proxyField) proxyField.value = "";
    if (apiKeyField) apiKeyField.value = "";
    if (rateSecField) rateSecField.value = "0";
    if (rateMinField) rateMinField.value = "0";
    if (contextKField) contextKField.value = "200";
    if (priorityField) priorityField.value = "1";
    if (maxTokensField) maxTokensField.value = "4096";
    if (thinkingField) thinkingField.value = "not_sent";
    if (effortField) effortField.value = "not_sent";
    if (streamingField) streamingField.checked = true;
    if (excludeField) excludeField.checked = false;

    $("#llm-dialog-title").textContent = "新建模型配置";
    const dlg = $("#llm-dialog");
    if (dlg) dlg.showModal();
  });

  window.activateLlm = async function(id) {
    try {
      await api("/api/llm/configs/activate", { method: "POST", body: { id } });
      await loadLlmModule();
      toast("已成功将模型配置设为默认激活！");
    } catch (e) { toast(e.message, true); }
  };

  window.deleteLlm = async function(id) {
    if (!confirm("确定要删除此模型配置吗？")) return;
    try {
      await api("/api/llm/configs/delete", { method: "POST", body: { id } });
      await loadLlmModule();
      toast("模型配置已删除。");
    } catch (e) { toast(e.message, true); }
  };

  window.editLlm = async function(id) {
    try {
      const data = await api("/api/llm/configs");
      const c = (data.configs || []).find(x => x.id === id);
      if (!c) return;

      $("#llm-id").value = c.id;
      $("#llm-name").value = c.name;
      $("#llm-format").value = c.format;
      $("#llm-model").value = c.model;
      $("#llm-base-url").value = c.base_url || "";
      $("#llm-proxy").value = c.proxy || "";
      $("#llm-api-key").value = "";
      $("#llm-rate-sec").value = c.rate_per_second || 0;
      $("#llm-rate-min").value = c.rate_per_minute || 0;
      $("#llm-context-k").value = c.context_window_k || 200;
      $("#llm-priority").value = c.priority || 1;
      $("#llm-max-tokens").value = c.max_tokens || 4096;
      $("#llm-thinking").value = c.thinking_type || "not_sent";
      $("#llm-effort").value = c.reasoning_effort || "not_sent";
      $("#llm-streaming").checked = c.streaming !== false;
      $("#llm-exclude").checked = Boolean(c.pool_exclude);

      $("#llm-dialog-title").textContent = "编辑模型配置";
      $("#llm-dialog")?.showModal();
    } catch (e) { toast(e.message, true); }
  };

  window.testLlmConnection = async function() {
    try {
      toast("正在测试模型端点连接与 TLS 握手...");
      const res = await api("/api/llm/test", { method: "POST", body: {} });
      toast(res.message || "连接测试成功！");
    } catch (e) { toast(e.message, true); }
  };

  $("#llm-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const payload = {
      id: $("#llm-id")?.value || undefined,
      name: $("#llm-name")?.value,
      format: $("#llm-format")?.value,
      model: $("#llm-model")?.value,
      base_url: $("#llm-base-url")?.value,
      proxy: $("#llm-proxy")?.value,
      api_key: $("#llm-api-key")?.value,
      rate_per_second: $("#llm-rate-sec")?.value,
      rate_per_minute: $("#llm-rate-min")?.value,
      context_window_k: $("#llm-context-k")?.value,
      priority: $("#llm-priority")?.value,
      max_tokens: $("#llm-max-tokens")?.value,
      thinking_type: $("#llm-thinking")?.value,
      reasoning_effort: $("#llm-effort")?.value,
      streaming: $("#llm-streaming")?.checked,
      pool_exclude: $("#llm-exclude")?.checked
    };
    try {
      await api("/api/llm/configs", { method: "POST", body: payload });
      $("#llm-dialog")?.close();
      await loadLlmModule();
      toast("模型配置已成功保存！");
    } catch (e) { toast(e.message, true); }
  });

  // Cairn Autonomous Multimodal Agent Module
  async function loadCairnModule() {
    const box = $("#cairn-content");
    if (!box) return;
    try {
      const data = await api("/api/cairn");
      const c = data.cairn || {};
      const actions = c.action_history || [];
      const memory = c.memory_store || [];
      const budget = c.autonomous_budget || {};

      box.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 1.25rem;">
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <strong style="font-size: 1.05rem; color: #0f172a;">全自主执行决策链路 (Decision Chain & Action Audit)</strong>
              <span style="font-size: 0.8rem; background: #e0f2fe; color: #0369a1; padding: 0.15rem 0.5rem; border-radius: 4px;">步数: ${budget.current_step}/${budget.max_steps}</span>
            </div>
            <div style="font-size: 0.85rem; color: #475569; margin-bottom: 0.75rem;">当前策略目标：${esc(c.current_goal)}</div>
            <div style="display: flex; flex-direction: column; gap: 0.75rem; max-height: 400px; overflow-y: auto;">
              ${actions.map(a => `
                <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <div style="font-size: 0.88rem; font-weight: 600; color: #0f172a;">${esc(a.action)}</div>
                    <div style="font-size: 0.8rem; color: #475569; font-family: monospace; margin-top: 0.15rem;">${esc(a.target)}</div>
                    <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.1rem;">时间: ${esc(a.timestamp)}</div>
                  </div>
                  <span style="font-size: 0.78rem; background: #dcfce7; color: #166534; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600;">${esc(a.status)}</span>
                </div>
              `).join("")}
            </div>
          </div>

          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <strong style="font-size: 1.05rem; color: #0f172a;">任务结果与 RAG 知识图谱 (Task Results & Memory)</strong>
              <span style="font-size: 0.8rem; color: #64748b;">${memory.length} 条资产/漏洞记录</span>
            </div>
            <div style="font-size: 0.85rem; color: #475569; margin-bottom: 0.75rem;">由策略驱动引擎综合归纳的资产状态、架构指纹与漏洞发现</div>
            <div style="display: flex; flex-direction: column; gap: 0.75rem; max-height: 400px; overflow-y: auto;">
              ${memory.map(m => `
                <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.75rem;">
                  <div style="font-size: 0.82rem; font-weight: 600; color: #0284c7; margin-bottom: 0.2rem;">${esc(m.key)} <span style="background: #f1f5f9; color: #475569; padding: 0.1rem 0.3rem; border-radius: 4px; font-size: 0.75rem;">${esc(m.category || 'General')}</span></div>
                  <div style="font-size: 0.85rem; color: #334155; line-height: 1.4;">${esc(m.value)}</div>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      `;
    } catch (e) {
      box.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  $("#cairn-trigger-btn")?.addEventListener("click", async () => {
    try {
      toast("正在触发全自主策略驱动推理循环...");
      await api("/api/cairn/trigger", { method: "POST", body: {} });
      await loadCairnModule();
      toast("全自主策略驱动循环步数已推进！");
    } catch (e) { toast(e.message, true); }
  });

  // Cyber-Combatant Arena Module
  async function loadArenaModule() {
    const box = $("#arena-content");
    if (!box) return;
    try {
      const data = await api("/api/arena");
      const a = data.arena || {};
      const strategists = a.strategists || [];
      const logs = a.plunder_logs || [];
      const conflicts = a.decision_conflicts || [];
      const pool = a.resource_pool || {};

      box.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem 1.25rem; flex-wrap: wrap; gap: 1rem;">
            <div>
              <span style="font-weight: 600; color: #0f172a; font-size: 1.1rem;">回合数: #${a.round}</span>
              <span style="margin-left: 1rem; font-size: 0.9rem; color: #64748b;">生存时间 TTL: <strong>${Math.floor(a.ttl_seconds_remaining / 60)}分${a.ttl_seconds_remaining % 60}秒</strong></span>
            </div>
            <div style="display: flex; gap: 1.5rem; font-size: 0.85rem; color: #334155;">
              <span>算力积分: <strong>${pool.credits} pts</strong></span>
              <span>代理额度: <strong>${pool.proxy_quota_gb} GB</strong></span>
              <span>活跃 Token: <strong>${pool.active_tokens}</strong></span>
            </div>
          </div>

          <!-- 模型自定义与切换控制面板 -->
          <div style="background: #f8fafc; border: 1px solid #38bdf8; border-radius: 12px; padding: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <strong style="font-size: 1.05rem; color: #0f172a;">⚙️ 自定义与切换参与委员会的模型 (Configure & Switch Participating Models)</strong>
              <button type="button" class="primary small" id="save-strategists-btn">💾 保存并应用模型配置</button>
            </div>
            <p style="font-size: 0.85rem; color: #475569; margin-bottom: 1rem;">您可以自由更改参与多智能体委员会博弈与仲裁的代理名称、底层模型（如 Gemini 1.5 Pro, Claude, GPT-4o, DeepSeek, Llama 等）及初始得分：</p>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;" id="strategists-editor-grid">
              ${strategists.map((s, idx) => `
                <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem;" data-strategist-card="${idx}">
                  <label style="font-size: 0.8rem; font-weight: 600; color: #334155;">代理名称:</label>
                  <input type="text" class="strat-name-input" value="${esc(s.name)}" style="padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.85rem;" />
                  <label style="font-size: 0.8rem; font-weight: 600; color: #334155;">底层大模型 (Model):</label>
                  <input type="text" class="strat-model-input" value="${esc(s.model)}" placeholder="例如: gemini-1.5-pro, claude-3-5, gpt-4o, llama-3" style="padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.85rem;" />
                  <div style="display: flex; gap: 0.5rem;">
                    <div style="flex: 1;">
                      <label style="font-size: 0.8rem; font-weight: 600; color: #334155;">初始得分:</label>
                      <input type="number" class="strat-score-input" value="${s.score}" step="0.1" style="width: 100%; padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.85rem;" />
                    </div>
                    <div style="flex: 1;">
                      <label style="font-size: 0.8rem; font-weight: 600; color: #334155;">子代理数:</label>
                      <input type="number" class="strat-sub-input" value="${s.subagents}" style="width: 100%; padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.85rem;" />
                    </div>
                  </div>
                </div>
              `).join("")}
            </div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.25rem;">
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
              <div style="margin-bottom: 0.75rem;"><strong style="font-size: 1.05rem; color: #0f172a;">战略家战力排行榜与权力交接 (Strategists & Command Lead)</strong></div>
              <div style="display: flex; flex-direction: column; gap: 0.85rem;">
                ${strategists.map((s, idx) => `
                  <div style="background: #fff; border: 2px solid ${s.is_lead ? '#22c55e' : '#cbd5e1'}; border-radius: 10px; padding: 1rem; position: relative;">
                    ${s.is_lead ? '<span style="position: absolute; top: 10px; right: 10px; background: #dcfce7; color: #166534; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">👑 指挥权 (Lead)</span>' : ''}
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem;">
                      <span style="font-weight: 700; color: #0284c7;">#${idx + 1}</span>
                      <strong style="color: #0f172a; font-size: 1rem;">${esc(s.name)}</strong>
                      <span style="background: #f1f5f9; color: #475569; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.75rem;">${esc(s.model)}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #059669; font-weight: 600; margin-bottom: 0.5rem;">综合得分: ${s.score} pts | 子代理集群: ${s.subagents} 个</div>
                    <div style="display: flex; gap: 1rem; font-size: 0.78rem; color: #64748b; background: #f8fafc; padding: 0.5rem; border-radius: 6px;">
                      <span>理论准确度: <strong>${s.dimensions.theoretical_accuracy}%</strong></span>
                      <span>执行成功率: <strong>${s.dimensions.execution_success_rate}%</strong></span>
                      <span>风险回报比: <strong>${s.dimensions.risk_reward_ratio}%</strong></span>
                    </div>
                    <div style="font-size: 0.78rem; color: #475569; margin-top: 0.4rem;">状态: <em>${esc(s.status)}</em></div>
                    <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px dashed #cbd5e1; display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center;">
                      <span style="font-size: 0.75rem; color: #475569; font-weight: 600;">已配备技能:</span>
                      ${(s.equipped_skills || []).map(sk => `<span style="background: #e0f2fe; color: #0369a1; padding: 0.15rem 0.45rem; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">⚔️ ${esc(sk)}</span>`).join("") || '<span style="font-size: 0.75rem; color: #94a3b8;">暂未装配技能</span>'}
                      <a href="#skills-arsenal" class="nav-item-link" style="font-size: 0.75rem; color: #7c3aed; text-decoration: underline; margin-left: auto;" onclick="document.querySelector('a[data-tab=\\'skills-arsenal\\']')?.click(); return false;">+ 从武器库装备</a>
                    </div>
                  </div>
                `).join("")}
              </div>
            </div>

            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
              <div style="margin-bottom: 0.75rem;"><strong style="font-size: 1.05rem; color: #0f172a;">掠夺与晋升日志 (Plunder & Evolution Logs)</strong></div>
              <div style="display: flex; flex-direction: column; gap: 0.75rem; max-height: 420px; overflow-y: auto;">
                ${logs.map(l => `
                  <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.75rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
                      <span style="font-weight: 600; color: #7c3aed; font-size: 0.85rem;">${esc(l.event)}</span>
                      <span style="font-size: 0.75rem; color: #64748b;">${esc(l.timestamp)}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #1e293b;">${esc(l.description)}</div>
                  </div>
                `).join("")}
              </div>
            </div>
          </div>

          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <strong style="font-size: 1.05rem; color: #0f172a;">⚡ 博弈动态流：三 LLM 代理关键决策冲突与仲裁日志 (Decision Conflict Stream)</strong>
              <span style="font-size: 0.8rem; background: #e0f2fe; color: #0369a1; padding: 0.15rem 0.5rem; border-radius: 4px;">共 ${conflicts.length} 条冲突记录</span>
            </div>
            <div style="font-size: 0.85rem; color: #475569; margin-bottom: 0.75rem;">实时显示三个 LLM 代理在每一轮对抗中产生的关键决策冲突、策略分歧与仲裁结果。</div>
            <div style="display: flex; flex-direction: column; gap: 0.75rem; max-height: 380px; overflow-y: auto;">
              ${conflicts.map(c => `
                <div style="background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 1rem; border-left: 4px solid #7c3aed;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                    <div>
                      <span style="font-weight: 700; color: #7c3aed; font-size: 0.9rem; margin-right: 0.5rem;">[第 ${c.round} 回合] ${esc(c.conflict_type)}</span>
                      <span style="font-size: 0.78rem; background: #f1f5f9; color: #475569; padding: 0.1rem 0.4rem; border-radius: 4px;">参与方: ${(c.agents_involved || []).join(" vs ")}</span>
                    </div>
                    <span style="font-size: 0.75rem; color: #64748b;">${esc(c.timestamp)}</span>
                  </div>
                  <div style="font-size: 0.88rem; color: #1e293b; margin-bottom: 0.4rem; line-height: 1.4;">${esc(c.description)}</div>
                  <div style="font-size: 0.8rem; color: #059669; background: #f0fdf4; padding: 0.4rem 0.6rem; border-radius: 6px; border: 1px solid #bbf7d0;">
                    <strong>仲裁结果:</strong> ${esc(c.resolution)}
                  </div>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      `;

      document.getElementById("save-strategists-btn")?.addEventListener("click", async () => {
        const cards = box.querySelectorAll("[data-strategist-card]");
        const newStrategists = [];
        cards.forEach((card, idx) => {
          const name = card.querySelector(".strat-name-input").value.trim();
          const model = card.querySelector(".strat-model-input").value.trim();
          const score = parseFloat(card.querySelector(".strat-score-input").value) || 80;
          const subagents = parseInt(card.querySelector(".strat-sub-input").value) || 3;
          const old = strategists[idx] || {};
          newStrategists.push({
            id: old.id || `strat-${idx+1}`,
            name: name || `Agent ${idx+1}`,
            model: model || "gemini-1.5-pro",
            is_lead: idx === 0,
            score: score,
            dimensions: old.dimensions || { theoretical_accuracy: 85, execution_success_rate: 85, risk_reward_ratio: 85 },
            subagents: subagents,
            status: old.status || "Active Committee"
          });
        });

        try {
          toast("正在保存并更新委员会模型配置...");
          await api("/api/arena/strategists", {
            method: "POST",
            body: { strategists: newStrategists }
          });
          toast("委员会参与模型已成功更新并切换！");
          loadArenaModule();
        } catch (e) {
          toast(e.message || String(e), true);
        }
      });
    } catch (e) {
      box.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`;
    }
  }

  let activeCategory = "all";
  let skillsSearchQuery = "";

  async function loadSkillsArsenalModule() {
    const box = $("#skills-content");
    const pillsBox = $("#skills-cat-pills");
    const searchInput = $("#skills-search");
    if (!box) return;

    try {
      const data = await api(`/api/skills?category=${encodeURIComponent(activeCategory)}&q=${encodeURIComponent(skillsSearchQuery)}`);
      const allSkills = data.skills || [];
      const categories = data.categories || {};
      const arenaData = await api("/api/arena");
      const strategists = (arenaData.arena && arenaData.arena.strategists) || [];

      // Update counters
      const totalCountEl = $("#skills-total-count");
      const catCountEl = $("#skills-cat-count");
      const scriptCountEl = $("#skills-script-count");
      const equippedCountEl = $("#skills-equipped-count");
      if (totalCountEl) totalCountEl.textContent = `${data.total || 181} 项`;
      if (catCountEl) catCountEl.textContent = `${Object.keys(categories).length} 大类`;
      const totalEquipped = strategists.reduce((acc, s) => acc + (s.equipped_skills ? s.equipped_skills.length : 0), 0);
      if (equippedCountEl) equippedCountEl.textContent = `${totalEquipped} 项`;

      // Render Category Filter Pills
      if (pillsBox) {
        const catEntries = Object.entries(categories);
        pillsBox.innerHTML = `
          <button type="button" class="skill-cat-pill ${activeCategory === 'all' ? 'active-pill' : ''}" data-cat="all" style="padding: 0.3rem 0.75rem; border-radius: 20px; border: 1px solid ${activeCategory === 'all' ? '#0284c7' : '#cbd5e1'}; background: ${activeCategory === 'all' ? '#0284c7' : '#fff'}; color: ${activeCategory === 'all' ? '#fff' : '#334155'}; font-size: 0.8rem; cursor: pointer; font-weight: 500;">
            🌟 全部全集 (${data.total || 181})
          </button>
          ${catEntries.map(([cName, cInfo]) => `
            <button type="button" class="skill-cat-pill ${activeCategory === cName ? 'active-pill' : ''}" data-cat="${esc(cName)}" style="padding: 0.3rem 0.75rem; border-radius: 20px; border: 1px solid ${activeCategory === cName ? '#0284c7' : '#cbd5e1'}; background: ${activeCategory === cName ? '#0284c7' : '#fff'}; color: ${activeCategory === cName ? '#fff' : '#334155'}; font-size: 0.8rem; cursor: pointer; font-weight: 500;">
              ${cInfo.icon || '🛡️'} ${esc(cName)}
            </button>
          `).join("")}
        `;

        pillsBox.querySelectorAll(".skill-cat-pill").forEach(btn => {
          btn.addEventListener("click", () => {
            activeCategory = btn.getAttribute("data-cat");
            loadSkillsArsenalModule();
          });
        });
      }

      // Bind search input
      if (searchInput && !searchInput.dataset.bound) {
        searchInput.dataset.bound = "true";
        searchInput.addEventListener("input", (e) => {
          skillsSearchQuery = e.target.value.trim();
          loadSkillsArsenalModule();
        });
      }

      if (allSkills.length === 0) {
        box.innerHTML = `<div class="muted" style="text-align: center; padding: 2rem;">没有找到匹配的技能项。</div>`;
        return;
      }

      // Render Skills Grid
      box.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1rem;">
          ${allSkills.map(sk => {
            return `
              <div style="background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem; display: flex; flex-direction: column; justify-content: space-between; gap: 0.75rem; transition: transform 0.15s, box-shadow 0.15s;" class="skill-card-item">
                <div>
                  <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.4rem;">
                    <div>
                      <span style="font-size: 0.75rem; background: #f1f5f9; color: #475569; padding: 0.15rem 0.45rem; border-radius: 4px; font-weight: 600;">${sk.category_icon || '🛡️'} ${esc(sk.category)}</span>
                      ${sk.phase ? `<span style="font-size: 0.75rem; background: #e0f2fe; color: #0369a1; padding: 0.15rem 0.45rem; border-radius: 4px; margin-left: 0.3rem;">${esc(sk.phase)}</span>` : ''}
                    </div>
                    <span style="font-size: 0.72rem; color: #94a3b8; font-family: monospace;">${esc(sk.id)}</span>
                  </div>
                  <h3 style="font-size: 1rem; font-weight: 700; color: #0f172a; margin: 0 0 0.3rem 0;">${esc(sk.name)}</h3>
                  <div style="font-size: 0.8rem; color: #64748b; font-family: monospace; margin-bottom: 0.5rem;">${esc(sk.english_name)}</div>
                  <p style="font-size: 0.84rem; color: #334155; line-height: 1.45; margin: 0 0 0.6rem 0;">${esc(sk.description || '全生命周期攻防战术能力单元')}</p>
                  
                  ${sk.trigger_words && sk.trigger_words.length ? `
                    <div style="display: flex; flex-wrap: wrap; gap: 0.25rem; margin-bottom: 0.5rem;">
                      ${sk.trigger_words.map(tw => `<span style="font-size: 0.72rem; background: #fef3c7; color: #92400e; padding: 0.1rem 0.35rem; border-radius: 4px;"># ${esc(tw)}</span>`).join("")}
                    </div>
                  ` : ''}

                  ${sk.scripts && sk.scripts.length ? `
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0.4rem 0.6rem; font-size: 0.78rem; color: #475569; display: flex; align-items: center; justify-content: space-between;">
                      <span>🐍 <strong>${sk.scripts.length}</strong> 个检测与利用脚本</span>
                      <span style="font-family: monospace; color: #0284c7;">${esc(sk.scripts[0].filename)}</span>
                    </div>
                  ` : ''}
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.4rem; padding-top: 0.5rem; border-top: 1px solid #f1f5f9;">
                  <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <select class="skill-strategist-select" style="flex: 1; padding: 0.35rem 0.5rem; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 0.8rem; background: #fff;">
                      <option value="">🎯 选择装备给战略家...</option>
                      ${strategists.map(s => {
                        const isEquipped = s.equipped_skills && s.equipped_skills.includes(sk.name);
                        return `<option value="${esc(s.id)}" data-strat-name="${esc(s.name)}">${isEquipped ? '✓ 已装备: ' : '+ 装配给: '} ${esc(s.name)}</option>`;
                      }).join("")}
                    </select>
                    <button type="button" class="primary small equip-skill-btn" data-skill-id="${esc(sk.id)}" data-skill-name="${esc(sk.name)}" style="white-space: nowrap; font-size: 0.78rem; padding: 0.35rem 0.6rem;">装配</button>
                  </div>
                  <button type="button" class="ghost small test-skill-btn" data-skill-id="${esc(sk.id)}" data-skill-name="${esc(sk.name)}" style="width: 100%; text-align: center; font-size: 0.78rem; color: #0284c7; border-color: #bae6fd; background: #f0f9ff;">⚡ 下发战术实战执行测试</button>
                </div>
              </div>
            `;
          }).join("")}
        </div>
      `;

      // Bind Equip buttons
      box.querySelectorAll(".equip-skill-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const card = btn.closest(".skill-card-item");
          const select = card.querySelector(".skill-strategist-select");
          const stratId = select.value;
          const skillName = btn.getAttribute("data-skill-name");
          const skillId = btn.getAttribute("data-skill-id");
          if (!stratId) {
            toast("请先选择要装备的目标战略家！", true);
            return;
          }
          try {
            toast(`正在将技能 [${skillName}] 装配至战略家...`);
            await api("/api/skills/equip", {
              method: "POST",
              body: { strategist_id: stratId, skill_id: skillId, skill_name: skillName, action: "equip" }
            });
            toast(`技能 [${skillName}] 已成功装配给战略家！`);
            await loadSkillsArsenalModule();
          } catch (e) {
            toast(e.message || String(e), true);
          }
        });
      });

      // Bind Execute buttons
      box.querySelectorAll(".test-skill-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const skillName = btn.getAttribute("data-skill-name");
          const skillId = btn.getAttribute("data-skill-id");
          const target = prompt(`请输入执行技能 [${skillName}] 的目标地址:`, "localhost");
          if (!target) return;
          try {
            toast(`正在执行技能 [${skillName}] 针对目标 ${target}...`);
            const res = await api("/api/skills/execute", {
              method: "POST",
              body: { skill_id: skillId, target: target }
            });
            toast(res.execution ? res.execution.output_summary : "技能下发执行成功！");
          } catch (e) {
            toast(e.message || String(e), true);
          }
        });
      });

    } catch (e) {
      box.innerHTML = `<div class="muted">实战技能库加载失败：${esc(e.message)}</div>`;
    }
  }

  $("#arena-tick-btn")?.addEventListener("click", async () => {
    try {
      toast("正在结算数字角斗场回合、三维得分与子代理掠夺...");
      await api("/api/arena/simulate", { method: "POST", body: {} });
      await loadArenaModule();
      toast("角斗场回合推进成功！资源与子代理完成重新分配。");
    } catch (e) { toast(e.message, true); }
  });
})();
