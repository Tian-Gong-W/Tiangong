(() => {
  "use strict";
  const csrf = document.querySelector('meta[name="tonmen-csrf"]').content;
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
      body.innerHTML = `<h3>当前没有等待批准的步骤</h3><p>当任务执行到需要人工确认的高风险步骤时，会显示在这里。</p><button class="danger" id="approve-btn" disabled>批准续行</button><button class="ghost" id="evidence-btn" disabled>查看证据</button>`;
      return;
    }
    const waiting = (m.steps || []).find(s => s.state === "waiting_approval");
    const failed = (m.steps || []).find(s => s.state === "failed" || s.state === "denied");
    if (waiting) {
      body.className = "approval-body";
      body.innerHTML = `<h3>${esc(waiting.tool)} 正在等待人工批准</h3><p>${esc(waiting.rationale || "此步骤需要明确授权后才能继续。")}</p><button class="danger" id="approve-btn">批准续行</button><button class="ghost" id="evidence-btn" ${(m.evidence || []).length ? "" : "disabled"}>查看证据</button>`;
      $("#approve-btn")?.addEventListener("click", approveCurrent);
      $("#evidence-btn")?.addEventListener("click", showEvidence);
    } else if (failed) {
      body.className = "approval-body";
      body.innerHTML = `<h3>${esc(failed.tool)} 执行失败</h3><p>${esc(failed.error || "工具执行未成功。")}</p><button class="ghost" id="evidence-btn" ${(m.evidence || []).length ? "" : "disabled"}>查看证据</button><button class="primary" id="retry-btn">重新执行</button>`;
      $("#evidence-btn")?.addEventListener("click", showEvidence);
      $("#retry-btn")?.addEventListener("click", () => openMissionDialog(m.target));
    } else {
      body.className = "approval-body idle";
      body.innerHTML = `<h3>当前没有等待批准的步骤</h3><p>高风险验证步骤需要人工明确批准。</p>${m.state === "running" ? `<button class="primary" id="resume-btn">续行任务</button>` : ""}<button class="ghost" id="evidence-btn" ${(m.evidence || []).length ? "" : "disabled"}>查看证据</button>`;
      $("#resume-btn")?.addEventListener("click", resumeCurrent);
      $("#evidence-btn")?.addEventListener("click", showEvidence);
    }
  }

  function updateDeck(m) {
    const current = $("#deck-current");
    if (current) current.textContent = m ? `${m.target}（${m.state}）` : "尚无任务";
    const approveBtn = $("#deck-approve");
    const evidenceBtn = $("#deck-evidence");
    const resumeBtn = $("#deck-resume");
    if (approveBtn) approveBtn.disabled = !(m && (m.steps || []).some(s => s.state === "waiting_approval"));
    if (evidenceBtn) evidenceBtn.disabled = !(m && (m.evidence || []).length);
    if (resumeBtn) resumeBtn.disabled = !(m && m.state === "running");
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

  // 绑定事件
  $("#deck-new-mission")?.addEventListener("click", () => openMissionDialog());
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
})();
