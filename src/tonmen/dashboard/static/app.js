(() => {
  "use strict";
  const csrf = document.querySelector('meta[name="tonmen-csrf"]').content;
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];
  const state = { missions: [], current: null, status: null, scope: null };
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const api = async (url, options = {}) => {
    const opts = { ...options, headers: { ...(options.headers || {}) } };
    if (opts.body && typeof opts.body !== "string") { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.body); }
    if ((opts.method || "GET") !== "GET") opts.headers["X-TONMEN-CSRF"] = csrf;
    const res = await fetch(url, opts); const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`); return data;
  };
  const toast = (message, error = false) => { const el = $("#toast"); el.textContent = message; el.className = `toast show${error ? " error" : ""}`; clearTimeout(toast.t); toast.t = setTimeout(() => el.className = "toast", 3200); };
  const fmtTime = (iso) => { if (!iso) return "—"; const d = new Date(iso); return Number.isNaN(d.valueOf()) ? "—" : d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"}); };
  const kindIcon = {host:"HOST",service:"SERVICE",web:"WEB",finding:"FINDING",technology:"TECH"};
  const stateLabel = {pending:"待行",running:"執行",waiting_approval:"候旨",succeeded:"已成",skipped:"止行",failed:"失敗",denied:"拒絕"};
  const stateMark = {pending:"○",running:"◌",waiting_approval:"…",succeeded:"✓",skipped:"—",failed:"!",denied:"×"};
  const componentIcon = {core:"◎",guard:"◇",registry:"⌁",intelligence:"◉",reasoner:"✺",loop:"∞"};

  function renderStatus() {
    const data = state.status;
    $("#status-grid").innerHTML = data.components.map(c => `<article class="status-card ${esc(c.tone)}"><div class="status-icon">${esc(componentIcon[c.id] || c.zh.slice(-1))}</div><div class="status-copy"><small>${esc(c.zh)} ${esc(c.en)}</small><strong>${esc(c.state)}</strong></div><span class="status-dot"></span></article>`).join("");
    const health = $("#health-pill"), ready = data.doctor.ready;
    health.querySelector("strong").textContent = ready ? "良好" : "需檢查";
    health.querySelector("strong").style.color = ready ? "var(--green)" : "var(--amber)";
    health.querySelector(".health-shield").style.color = ready ? "var(--green)" : "var(--amber)";
    health.title = data.doctor.checks.map(c => `${c.ok ? "OK" : "MISS"} ${c.name}: ${c.detail}`).join("\n");
  }

  function renderScope() {
    $("#scope-list").innerHTML = state.scope.allowed.map(item => {
      const icon = item.rule.includes("/") ? "⌘" : item.rule.startsWith("*.") ? "◎" : item.rule === "localhost" ? "▣" : "◉";
      return `<div class="scope-row"><span class="scope-icon">${icon}</span><span class="scope-rule" title="${esc(item.rule)}">${esc(item.rule)}</span><span class="scope-badge ${item.default ? "default" : ""}">${item.default ? "內建" : "已授權"}</span><span style="color:var(--green);font-size:17px">✓</span>${item.default ? "" : `<button class="scope-remove" data-remove-scope="${esc(item.rule)}">移除</button>`}</div>`;
    }).join("");
    $$('[data-remove-scope]').forEach(btn => btn.addEventListener("click", async () => {
      try { state.scope = await api("/api/scope/remove", {method:"POST", body:{target:btn.dataset.removeScope}}); renderScope(); toast(`已移除 Scope: ${btn.dataset.removeScope}`); }
      catch (e) { toast(e.message, true); }
    }));
  }

  function renderMissionSelect(preferredId = null) {
    const sel = $("#mission-select");
    const wanted = preferredId || state.current?.id || sel.value;
    sel.innerHTML = state.missions.length ? state.missions.map(m => `<option value="${esc(m.id)}">${esc(m.target)} · ${esc(m.state)} · ${esc(m.id.slice(0,8))}</option>`).join("") : `<option value="">尚無任務</option>`;
    if (wanted && state.missions.some(m => m.id === wanted)) sel.value = wanted;
  }

  function renderMission() {
    const m = state.current;
    $("#mission-empty").classList.toggle("hidden", !!m); $("#mission-body").classList.toggle("hidden", !m);
    if (!m) {
      $("#intel-list").innerHTML = `<div class="muted">尚無可證實情報。</div>`;
      $("#reason-card").className = "reason-card empty"; $("#reason-card").innerHTML = `<span class="decision-action">NO DECISION</span><p>等待天鑑提供證據。</p>`;
      $("#approve-btn").disabled = true; $("#evidence-btn").disabled = true;
      $("#chronicle-list").innerHTML = `<div class="muted">尚無記錄。</div>`; $("#intel-count").textContent = "0"; $("#graph-count").textContent = "0"; $("#graph-summary").textContent = "等待任務資料。"; return;
    }
    $("#mission-target").textContent = m.target; $("#mission-state").textContent = m.state; $("#mission-state").className = `state-pill ${m.state}`;
    $("#mission-steps").innerHTML = m.steps.map((s,i) => {
      const detail = s.error ? `錯誤：${s.error}` : (s.rationale || s.target);
      return `<div class="step"><div class="step-index">${String(i+1).padStart(2,"0")}</div><div><strong>${esc(s.tool)}</strong><small title="${esc(detail)}" style="${s.error ? "color:var(--red)" : ""}">${esc(detail)}</small></div><span class="step-state ${esc(s.state)}">${esc(stateMark[s.state] || "")} ${esc(stateLabel[s.state] || s.state)}</span></div>`;
    }).join("");

    $("#intel-count").textContent = m.intelligence.length;
    $("#intel-list").innerHTML = m.intelligence.length ? m.intelligence.slice(-12).reverse().map(n => {
      const kind = n.kind.replace("intelligence.",""); const sev = n.metadata?.severity || "";
      return `<div class="intel-row"><span class="intel-kind">${esc(kindIcon[kind] || kind)}</span><strong>${esc(n.label)}</strong>${sev && sev !== "info" ? `<span class="sev ${esc(sev)}">${esc(sev)}</span>` : "<span></span>"}</div>`;
    }).join("") : `<div class="muted">${m.state === "failed" ? "任務在產生可解析 Intelligence 前失敗。若有原始執行證據，可從右側「查看證據」檢查 stdout / stderr。" : "原始 Evidence 已保存，但目前沒有可確定解析的 Intelligence Fact。"}</div>`;

    const latest = m.reasoning.at(-1);
    if (latest) {
      const action = latest.metadata?.action || latest.kind.replace("reasoning.",""); const human = latest.metadata?.requires_human;
      $("#reason-card").className = "reason-card";
      $("#reason-card").innerHTML = `<span class="decision-action">${esc(action.toUpperCase())}</span><p>${esc(latest.label)}</p><div class="decision-basis">${human ? "需人決" : "可自治"} · ${(latest.metadata?.basis_fact_ids || []).length} fact(s) 為據</div>`;
    } else {
      $("#reason-card").className = "reason-card empty"; $("#reason-card").innerHTML = `<span class="decision-action">NO DECISION</span><p>${m.state === "failed" ? "執行失敗，請先查看失敗步驟與原始證據。" : "等待天鑑提供證據。"}</p>`;
    }

    const waiting = m.steps.find(s => s.state === "waiting_approval"), failed = m.steps.find(s => s.state === "failed" || s.state === "denied"), approval = $("#approval-body");
    if (waiting) {
      approval.className = "approval-body";
      approval.innerHTML = `<div class="approval-icon">♙</div><h3>${esc(waiting.tool)} 正在等待人工審批</h3><p>執行將進入需要明確授權的驗證步驟。<br>${esc(waiting.rationale || "此驗證步驟需要由人明確授權。")}</p><button class="danger" id="approve-btn">✓ 批准續行</button><button class="ghost" id="evidence-btn"${m.evidence.length ? "" : " disabled"}>◉ 查看證據</button>`;
      $("#approve-btn").addEventListener("click", approveCurrent); $("#evidence-btn").addEventListener("click", showEvidence);
    } else if (failed) {
      approval.className = "approval-body";
      approval.innerHTML = `<div class="approval-icon">!</div><h3>${esc(failed.tool)} 執行失敗</h3><p>${esc(failed.error || "工具執行未成功。")}</p><button class="ghost" id="evidence-btn"${m.evidence.length ? "" : " disabled"}>◉ 查看原始證據</button><button class="primary" id="retry-btn">▶ 重新執行任務</button>`;
      $("#evidence-btn").addEventListener("click", showEvidence); $("#retry-btn").addEventListener("click", () => openMissionDialog(m.target));
    } else {
      approval.className = "approval-body idle";
      approval.innerHTML = `<div class="approval-icon">鎖</div><h3>目前無候旨步驟</h3><p>高風險驗證若需越過天律，必須由人明示批准。</p>${m.state === "running" ? `<button class="primary" id="resume-btn">∞ 新預算續行</button>` : ""}<button class="ghost" id="evidence-btn"${m.evidence.length ? "" : " disabled"}>◉ 查看證據</button>`;
      $("#resume-btn")?.addEventListener("click", resumeCurrent); $("#evidence-btn").addEventListener("click", showEvidence);
    }
    renderChronicle(m); renderGraph(m);
  }

  function renderChronicle(m) {
    const events = [{time:m.started_at,text:`任務建立 / Mission Created · ${m.target}`,tone:""}];
    m.evidence.forEach(e => events.push({time:e.finished_at,text:`${e.tool} 執行${e.exit_code === 0 ? "完成" : "失敗"} · exit ${e.exit_code}`,tone:e.exit_code === 0 ? "" : "danger"}));
    m.observations.forEach(o => events.push({time:o.captured_at,text:`證據記錄 / ${o.summary}`,tone:""}));
    const failed = m.steps.find(s => s.state === "failed" || s.state === "denied"); if (failed && !m.evidence.some(e => e.tool === failed.tool && e.exit_code !== 0)) events.push({time:m.finished_at,text:`執行失敗 / ${failed.tool}: ${failed.error || "unknown error"}`,tone:"danger"});
    const waiting = m.steps.find(s => s.state === "waiting_approval"); if (waiting) events.push({time:null,text:`需要審批 / Approval Required (${waiting.tool})`,tone:"danger"});
    const stop = m.loop.filter(n => n.kind === "loop.stop").at(-1); if (stop) events.push({time:null,text:`天衡停止 / ${stop.metadata?.reason || stop.label}`,tone:"warn"});
    $("#chronicle-list").innerHTML = events.map(ev => `<div class="timeline-row ${ev.tone}"><span class="timeline-time">${fmtTime(ev.time)}</span><span class="timeline-dot"></span><span class="timeline-text">${esc(ev.text)}</span></div>`).join("");
  }

  function renderGraph(m) {
    $("#graph-count").textContent = m.graph.nodes.length;
    const counts = m.graph.nodes.reduce((acc,n) => { const k = n.kind.split(".")[0]; acc[k] = (acc[k] || 0) + 1; return acc; }, {});
    $("#graph-summary").textContent = `${m.graph.nodes.length} nodes · ${m.graph.edges.length} edges · ${counts.evidence || 0} evidence · ${counts.observation || m.observations.length || 0} observations · ${counts.intelligence || 0} intelligence · ${counts.reasoning || 0} decisions`;
  }

  async function loadMission(id) {
    if (!id) { state.current = null; renderMissionSelect(); renderMission(); return; }
    try {
      const loaded = await api(`/api/missions/${encodeURIComponent(id)}`);
      state.current = loaded;
      renderMissionSelect(id);
      renderMission();
    } catch (e) {
      state.current = null;
      renderMissionSelect(id);
      renderMission();
      toast(`無法載入任務詳情：${e.message}`, true);
    }
  }
  async function refreshAll(preferredId = null) {
    try {
      const [status, scope, ms] = await Promise.all([api("/api/status"),api("/api/scope"),api("/api/missions")]);
      state.status = status; state.scope = scope; state.missions = ms.missions;
      const id = preferredId || state.current?.id || state.missions[0]?.id || null;
      renderStatus(); renderScope(); renderMissionSelect(id);
      await loadMission(id);
    } catch (e) { toast(e.message,true); }
  }
  async function approveCurrent() { if (!state.current) return; if (!confirm("確認批准目前候旨步驟？此批准僅綁定當前 Tool + Target，且為一次性 Grant。")) return; try { toast("天契已受命，正在續行…"); state.current = await api(`/api/missions/${state.current.id}/approve`, {method:"POST",body:{}}); await refreshAll(state.current.id); toast("批准已執行，任務狀態已更新。"); } catch (e) { toast(e.message,true); } }
  async function resumeCurrent() { if (!state.current) return; try { toast("開啟新的受限天衡預算…"); state.current = await api(`/api/missions/${state.current.id}/resume`, {method:"POST",body:{}}); await refreshAll(state.current.id); toast("任務已續行。"); } catch (e) { toast(e.message,true); } }
  function showEvidence() {
    const m = state.current; if (!m || !m.evidence.length) { toast("此任務沒有可用的原始證據。舊版 failed 任務可能未保存失敗輸出。", true); return; }
    const dialog = $("#evidence-dialog"), tabs = $("#evidence-tabs"), pre = $("#evidence-content");
    tabs.innerHTML = m.evidence.map((e,i)=>`<button data-ev="${i}">${esc(e.tool)} · exit ${e.exit_code} · ${esc(e.id.slice(0,8))}</button>`).join("");
    const show = i => { const e=m.evidence[i]; pre.textContent = `$ ${e.argv.join(" ")}\nexit: ${e.exit_code}\n\n--- stdout ---\n${e.stdout || "(empty)"}\n\n--- stderr ---\n${e.stderr || "(empty)"}`; };
    $$('[data-ev]').forEach(b=>b.addEventListener("click",()=>show(Number(b.dataset.ev)))); show(m.evidence.length-1); dialog.showModal();
  }
  function openMissionDialog(target = "") { $("#mission-input").value = target || ""; $("#mission-dialog").showModal(); setTimeout(()=>$("#mission-input").focus(),30); }

  $("#new-mission-btn").textContent = "▶ 執行任務";
  $("#empty-new-mission-btn").textContent = "▶ 執行任務";
  $("#new-mission-btn").addEventListener("click", () => openMissionDialog()); $("#empty-new-mission-btn").addEventListener("click", () => openMissionDialog());
  const dialogTitle = $("#mission-dialog h2"); if (dialogTitle) dialogTitle.textContent = "建立並執行任務";
  const dialogSubmit = $("#mission-form .dialog-actions .primary"); if (dialogSubmit) dialogSubmit.textContent = "▶ 開始執行";
  $$(".close-dialog").forEach(b=>b.addEventListener("click",()=>$("#mission-dialog").close())); $$(".close-evidence").forEach(b=>b.addEventListener("click",()=>$("#evidence-dialog").close()));
  $("#refresh-btn").addEventListener("click",()=>refreshAll($("#mission-select").value || null)); $("#mission-select").addEventListener("change",e=>loadMission(e.target.value));
  $("#mission-form").addEventListener("submit", async e => {
    e.preventDefault(); const target = $("#mission-input").value.trim(); if (!target) return;
    try {
      $("#mission-dialog").close(); toast(`正在執行受控任務：${target}`);
      const m = await api("/api/missions/start", {method:"POST",body:{target,max_iterations:Number($("#max-iterations").value),max_executions:Number($("#max-executions").value),max_duration_seconds:Number($("#max-duration").value),max_repeat_decisions:2}});
      state.current = m; await refreshAll(m.id);
      toast(m.state === "failed" ? "任務執行失敗；已切換到失敗步驟與證據。" : "任務已執行並記入天冊。", m.state === "failed");
    } catch (err) { toast(err.message,true); }
  });
  $("#scope-form").addEventListener("submit", async e => { e.preventDefault(); const input=$("#scope-input"), target=input.value.trim(); if(!target)return; try { state.scope=await api("/api/scope/add",{method:"POST",body:{target}}); input.value="";renderScope();toast(`已納入 Scope: ${target}`); } catch(err){toast(err.message,true);} });
  $$(".nav-item").forEach(btn=>btn.addEventListener("click",()=>{ $$(".nav-item").forEach(x=>x.classList.remove("active")); btn.classList.add("active"); document.getElementById(btn.dataset.scroll)?.scrollIntoView({behavior:"smooth",block:"start"}); }));
  refreshAll();
  setInterval(async () => { if (document.hidden) return; try { const ms=await api("/api/missions"); state.missions=ms.missions; renderMissionSelect(state.current?.id || null); if(state.current) await loadMission(state.current.id); } catch (_) {} }, 5000);
})();
