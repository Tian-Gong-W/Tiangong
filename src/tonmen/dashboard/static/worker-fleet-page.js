(() => {
  "use strict";

  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  let busy = false;

  function toast(message, bad = false) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message;
    el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.className = "toast"; }, 3500);
  }

  async function api(url, options = {}) {
    const opts = {...options, cache:"no-store", headers:{...(options.headers || {})}};
    if ((opts.method || "GET") !== "GET") {
      opts.headers["X-TONMEN-CSRF"] = csrf;
      opts.headers["Content-Type"] = "application/json";
      opts.body ||= "{}";
    }
    const response = await fetch(url, opts);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data;
  }

  function state(worker) {
    if (worker.draining || worker.scheduler?.draining) return ["维护中", "warn"];
    const probe = worker.last_probe;
    if (probe?.ready) return ["可用", "ready"];
    if (!worker.secret_configured) return ["未配置", "bad"];
    if (probe && !probe.ready) return ["不可用", "bad"];
    return ["未检查", "warn"];
  }

  function renderSummary(data) {
    const history = data.historical || {};
    const workers = data.workers || [];
    const scheduler = data.scheduler || {};
    const ready = workers.filter(item => item.last_probe?.ready).length;
    const inflight = workers.reduce((sum,item) => sum + Number(item.scheduler?.inflight ?? item.inflight ?? 0), 0);
    const cards = [
      ["执行方式", data.execution_mode === "worker" ? "远程节点" : "本机"],
      ["节点", workers.length],
      ["可用", ready],
      ["执行中", inflight],
      ["排队", scheduler.queue_depth || 0],
      ["历史步骤", history.remote_steps || 0],
    ];
    $("#fleet-summary").innerHTML = cards.map(([label,value]) => `<div class="fleet-summary-card"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
    const mode = $("#fleet-mode");
    mode.textContent = data.execution_mode === "worker" ? "远程节点" : "本机";
    mode.className = `module-badge ${data.execution_mode === "worker" ? "ok" : "blue"}`;
  }

  function workerCard(worker) {
    const [label,tone] = state(worker);
    const history = worker.history || {};
    const probe = worker.last_probe;
    const tools = probe?.tools || {};
    const sched = worker.scheduler || {};
    const inflight = sched.inflight ?? worker.inflight ?? 0;
    const max = sched.max_concurrency ?? worker.max_concurrency ?? 1;
    const available = sched.available_slots ?? worker.available_slots ?? Math.max(0, max - inflight);
    const draining = Boolean(sched.draining ?? worker.draining);
    const toolBadges = Object.entries(tools).map(([name,info]) => `<span class="${info.ready ? "ready" : "bad"}">${esc(name)} ${info.ready ? "✓" : "×"}</span>`).join("");
    return `<article class="worker-card ${worker.secret_configured ? "active" : ""}">
      <div class="worker-card-head"><h3>${esc(worker.id)}<small>${esc(worker.region || "default")} · ${(worker.tags || []).map(esc).join(" · ") || "通用"}</small></h3><span class="worker-state ${tone}">${esc(label)}</span></div>
      <div class="worker-meta"><span>地址</span><code>${esc(worker.url)}</code><span>并发</span><strong>${esc(inflight)} / ${esc(max)}</strong><span>空闲</span><strong>${esc(available)}</strong><span>认证</span><strong>${worker.secret_configured ? "已配置" : "未配置"}</strong></div>
      <div class="worker-history"><span>步骤 <b>${esc(history.steps || 0)}</b></span><span>成功 <b>${esc(history.succeeded || 0)}</b></span><span>失败 <b>${esc(history.failed || 0)}</b></span><span>证据 <b>${esc(history.evidence || 0)}</b></span></div>
      ${toolBadges ? `<div class="worker-tools">${toolBadges}</div>` : ""}
      <div class="worker-actions"><button class="ghost" type="button" data-worker-probe="${esc(worker.id)}">检查</button><button class="${draining ? "primary" : "ghost"}" type="button" data-worker-drain="${esc(worker.id)}" data-draining="${draining ? "1" : "0"}">${draining ? "恢复" : "维护"}</button></div>
      ${probe ? `<div class="worker-probe">${probe.ready ? "✓" : "△"} ${esc(probe.detail || "")} · ${esc(probe.ready_tools ?? 0)}/${esc(probe.total_tools ?? 0)} 工具可用</div>` : ""}
    </article>`;
  }

  function renderWorkers(data) {
    const workers = data.workers || [];
    $("#worker-grid").innerHTML = workers.length ? workers.map(workerCard).join("") : `<div class="fleet-empty">还没有配置执行节点，当前使用本机执行。</div>`;
  }

  function renderRouting(data) {
    const route = data.routing || {};
    const scheduler = data.scheduler || {};
    $("#routing-state").innerHTML = `
      <div>队列 <code>${esc(scheduler.queue_depth || 0)} / ${esc(scheduler.max_queue_size || route.max_queue_size || 128)}</code></div>
      <div>等待上限 <code>${esc(scheduler.queue_timeout_seconds || route.queue_timeout_seconds || 30)}s</code></div>
      <div>平均等待 <code>${esc(scheduler.average_wait_ms || 0)}ms</code></div>
      <div>指定节点 <code>${esc(route.worker_id || "自动")}</code></div>
      <div>区域 <code>${esc(route.region || "不限")}</code></div>
      <div>标签 <code>${esc((route.tags || []).join(", ") || "不限")}</code></div>
      <div class="routing-note">维护只停止新任务，不会中断正在执行的任务。连接结果不确定时不会自动在另一节点重复执行。</div>`;
  }

  function bindActions() {
    document.querySelectorAll("[data-worker-probe]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const id = button.dataset.workerProbe;
      try {
        busy = true; button.disabled = true;
        const result = await api(`/api/workers/${encodeURIComponent(id)}/probe`, {method:"POST"});
        toast(result.ready ? `${id}: 可用` : `${id}: ${result.detail}`, !result.ready);
        await refresh();
      } catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));

    document.querySelectorAll("[data-worker-drain]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const id = button.dataset.workerDrain;
      const draining = button.dataset.draining === "1";
      const action = draining ? "activate" : "drain";
      try {
        busy = true; button.disabled = true;
        const result = await api(`/api/workers/${encodeURIComponent(id)}/${action}`, {method:"POST"});
        toast(`${id}: ${result.draining ? "已进入维护，不再接收新任务" : "已恢复接收任务"}`);
        await refresh();
      } catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));
  }

  async function refresh() {
    try {
      $("#fleet-alert").classList.add("hidden");
      const data = await api("/api/workers");
      renderSummary(data); renderWorkers(data); renderRouting(data); bindActions();
      $("#fleet-updated").textContent = new Date().toLocaleTimeString();
    } catch (error) {
      const alert = $("#fleet-alert"); alert.textContent = error.message || String(error); alert.classList.remove("hidden");
    }
  }

  $("#fleet-refresh")?.addEventListener("click", refresh);
  setInterval(() => { if (!document.hidden && !busy) refresh(); }, 5000);
  refresh();
})();
