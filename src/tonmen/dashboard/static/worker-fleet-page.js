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
    const probe = worker.last_probe;
    if (probe?.ready) return ["READY", "ready"];
    if (!worker.secret_configured) return ["SECRET MISSING", "bad"];
    if (probe && !probe.ready) return ["UNAVAILABLE", "bad"];
    return ["NOT PROBED", "warn"];
  }

  function renderSummary(data) {
    const history = data.historical || {};
    const workers = data.workers || [];
    const ready = workers.filter(item => item.last_probe?.ready).length;
    const cards = [
      ["Execution mode", data.execution_mode || "local"],
      ["Workers configured", workers.length],
      ["Workers ready", ready],
      ["Remote steps", history.remote_steps || 0],
      ["Remote evidence", history.evidence_records || 0],
    ];
    $("#fleet-summary").innerHTML = cards.map(([label,value]) => `<div class="fleet-summary-card"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
    const mode = $("#fleet-mode");
    mode.textContent = (data.execution_mode || "local").toUpperCase();
    mode.className = `module-badge ${data.execution_mode === "worker" ? "ok" : "blue"}`;
  }

  function workerCard(worker) {
    const [label,tone] = state(worker);
    const history = worker.history || {};
    const probe = worker.last_probe;
    const tools = probe?.tools || {};
    const toolBadges = Object.entries(tools).map(([name,info]) => `<span class="${info.ready ? "ready" : "bad"}">${esc(name)} ${info.ready ? "✓" : "×"}</span>`).join("");
    return `<article class="worker-card ${worker.secret_configured ? "active" : ""}">
      <div class="worker-card-head"><h3>${esc(worker.id)}<small>${esc(worker.region || "default")} · ${(worker.tags || []).map(esc).join(" · ") || "no tags"}</small></h3><span class="worker-state ${tone}">${esc(label)}</span></div>
      <div class="worker-meta"><span>Endpoint</span><code>${esc(worker.url)}</code><span>Weight</span><strong>${esc(worker.weight)}</strong><span>Secret env</span><code>${esc(worker.secret_env)}</code><span>Secret configured</span><strong>${worker.secret_configured ? "yes" : "no"}</strong></div>
      <div class="worker-history"><span>steps <b>${esc(history.steps || 0)}</b></span><span>success <b>${esc(history.succeeded || 0)}</b></span><span>failed <b>${esc(history.failed || 0)}</b></span><span>evidence <b>${esc(history.evidence || 0)}</b></span></div>
      ${toolBadges ? `<div class="worker-tools">${toolBadges}</div>` : ""}
      <div class="worker-actions"><button class="ghost" type="button" data-worker-probe="${esc(worker.id)}">检查 Worker</button></div>
      ${probe ? `<div class="worker-probe">${probe.ready ? "✓" : "△"} ${esc(probe.detail || "")} · ${esc(probe.ready_tools ?? 0)}/${esc(probe.total_tools ?? 0)} tools ready</div>` : ""}
    </article>`;
  }

  function renderWorkers(data) {
    const workers = data.workers || [];
    $("#worker-grid").innerHTML = workers.length ? workers.map(workerCard).join("") : `<div class="fleet-empty">尚未配置 TONMEN_WORKERS。当前仍由本机 Executor 执行。</div>`;
  }

  function renderRouting(data) {
    const route = data.routing || {};
    $("#routing-state").innerHTML = `
      <div>Strategy: <code>${esc(data.strategy || "health-gated weighted least-use")}</code></div>
      <div>Probe before dispatch: <code>${route.probe_before_dispatch ? "yes" : "no"}</code></div>
      <div>Job TTL: <code>${esc(route.job_ttl_seconds || 60)}s</code></div>
      <div>Preferred worker: <code>${esc(route.worker_id || "AUTO")}</code></div>
      <div>Region: <code>${esc(route.region || "ANY")}</code></div>
      <div>Required tags: <code>${esc((route.tags || []).join(", ") || "ANY")}</code></div>
      <div style="margin-top:8px">Dispatch timeout/connection ambiguity is fail-closed. TONMEN does not automatically run the same active job on a second worker after POST begins.</div>
      <div style="margin-top:8px">Secret values: <code>NEVER EXPOSED</code> · Approval Token: <code>NEVER SENT</code> · raw shell/argv: <code>NEVER SENT</code></div>`;
  }

  function bindActions() {
    document.querySelectorAll("[data-worker-probe]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const id = button.dataset.workerProbe;
      try {
        busy = true; button.disabled = true;
        const result = await api(`/api/workers/${encodeURIComponent(id)}/probe`, {method:"POST"});
        toast(`${id}: ${result.detail}`, !result.ready);
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
