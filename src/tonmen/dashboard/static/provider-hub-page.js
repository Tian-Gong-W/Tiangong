(() => {
  "use strict";

  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
  let busy = false;

  function toast(message, bad = false) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message;
    el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.className = "toast"; }, 3600);
  }

  function alertBox(message = "") {
    const el = $("#hub-alert");
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("hidden", !message);
  }

  async function api(url, options = {}) {
    const opts = {...options, cache:"no-store", headers:{...(options.headers || {})}};
    if ((opts.method || "GET") !== "GET") {
      opts.headers["X-TONMEN-CSRF"] = csrf;
      if (!opts.body) opts.body = "{}";
      opts.headers["Content-Type"] = "application/json";
    }
    const response = await fetch(url, opts);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data;
  }

  function providerState(provider) {
    const probe = provider.last_probe;
    if (probe?.ready) return ["READY", "ready"];
    if (provider.auth_mode === "api_key") {
      return provider.key_configured ? ["KEY READY", "ready"] : ["KEY MISSING", "bad"];
    }
    if (!provider.installed) return ["CLI MISSING", "bad"];
    if (probe && !probe.ready) return ["LOGIN CHECK", "warn"];
    return [provider.enabled_in_pool ? "CHECK LOGIN" : "AVAILABLE", "warn"];
  }

  function renderSummary(hub) {
    const providers = hub.providers || [];
    const ready = providers.filter(item => providerState(item)[1] === "ready").length;
    const usage = hub.historical_usage || {};
    const pool = hub.pool || [];
    const html = [
      ["Pool size", pool.length],
      ["Providers ready", ready],
      ["Subagent calls", usage.total_calls || 0],
      ["Subagent tokens", usage.total_tokens || 0],
      ["Token budget", hub.token_budget || 0],
    ].map(([label, value]) => `<div class="hub-summary-card"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
    $("#hub-summary").innerHTML = html;
    $("#pool-state").textContent = pool.length ? `${pool.length} IN POOL` : "POOL DISABLED";
    $("#pool-state").className = `module-badge ${pool.length ? "ok" : "blue"}`;
    $("#token-total").textContent = `${usage.total_tokens || 0} TOKENS`;
  }

  function renderLead(data) {
    const cfg = data.config || {};
    const current = data.current;
    const state = $("#lead-state");
    const body = $("#lead-body");
    const active = Boolean(cfg.active);
    state.textContent = active ? "MODEL ACTIVE" : cfg.provider && cfg.provider !== "disabled" ? "FALLBACK" : "DISABLED";
    state.className = `module-badge ${active ? "ok" : cfg.provider && cfg.provider !== "disabled" ? "warn" : "blue"}`;
    if (!current) {
      body.innerHTML = `<div class="lead-runtime"><div><span>Provider</span><strong>${esc(cfg.provider || "disabled")}</strong></div><div><span>Model</span><strong>${esc(cfg.model || "—")}</strong></div><div><span>Key configured</span><strong>${cfg.key_configured ? "yes" : "no"}</strong></div></div><div class="hub-empty">尚无 Lead Directive。新 Mission 进入 Council 后会显示当前主导目标。</div>`;
      return;
    }
    const md = current.latest_directive?.metadata || {};
    const telemetry = current.telemetry || {};
    body.innerHTML = `<div class="lead-runtime"><div><span>Provider / model</span><strong>${esc(md.provider || cfg.provider || "deterministic")} · ${esc(md.model || cfg.model || "—")}</strong></div><div><span>Round</span><strong>${esc(current.rounds_completed || 0)} / ${esc(current.target_rounds || 8)}</strong></div><div><span>Lead tokens</span><strong>${esc(telemetry.total_tokens || 0)}</strong></div></div><div class="lead-directive"><h3>${esc(md.focus || "Current directive")}</h3><p>${esc(md.objective || "—")}</p><code>${esc(md.recommended_action || "—")} · confidence ${esc(md.confidence ?? "—")}</code>${md.error ? `<p>${esc(md.error)}</p>` : ""}</div>`;
  }

  function providerCard(provider) {
    const [label, tone] = providerState(provider);
    const usage = provider.usage || {};
    const loginButton = provider.auth_mode === "browser_login" && provider.installed
      ? `<button class="primary" type="button" data-provider-login="${esc(provider.id)}">网页登录</button>`
      : "";
    const probeLabel = provider.auth_mode === "api_key" ? "检查 Key" : "检查连接";
    const authValue = provider.auth_mode === "api_key"
      ? `${provider.key_env || "KEY"} · ${provider.key_configured ? "configured" : "not configured"}`
      : `${provider.executable || "CLI"} · ${provider.installed ? "installed" : "missing"}`;
    const probe = provider.last_probe;
    return `<article class="provider-card ${provider.enabled_in_pool ? "pool-enabled" : ""}"><div class="provider-card-head"><div><h3>${esc(provider.label)}<small>${esc(provider.transport)} · strength ${esc(provider.strength)}</small></h3></div><span class="provider-state ${tone}">${esc(label)}</span></div><div class="provider-meta"><span>Pool</span><strong>${provider.enabled_in_pool ? "enabled" : "not enabled"}</strong><span>Auth</span><code>${esc(authValue)}</code><span>Model</span><code>${esc(provider.default_model || "provider default")}</code><span>Cost weight</span><strong>${esc(provider.cost_weight ?? "—")}</strong></div><div class="provider-usage"><span>calls <b>${esc(usage.calls || 0)}</b></span><span>model <b>${esc(usage.model_calls || 0)}</b></span><span>tokens <b>${esc(usage.total_tokens || 0)}</b></span><span>failures <b>${esc(usage.failures || 0)}</b></span></div><div class="provider-actions">${loginButton}<button class="ghost" type="button" data-provider-probe="${esc(provider.id)}">${esc(probeLabel)}</button></div>${probe ? `<div class="provider-probe">${probe.ready ? "✓" : "△"} ${esc(probe.detail || "")}</div>` : ""}</article>`;
  }

  function renderProviders(hub) {
    $("#provider-grid").innerHTML = (hub.providers || []).map(providerCard).join("") || `<div class="hub-empty">没有 Provider 配置。</div>`;
  }

  function renderDistribution(hub) {
    const rows = (hub.distribution || []).filter(item => item.calls || item.tokens);
    $("#distribution-list").innerHTML = rows.length ? rows.map(item => `<div class="distribution-row"><strong>${esc(item.provider)}</strong><progress max="100" value="${Math.max(0, Math.min(100, Number(item.token_share_percent) || 0))}"></progress><span>${esc(item.token_share_percent)}% · ${esc(item.tokens)} tok · ${esc(item.calls)} calls</span></div>`).join("") : `<div class="hub-empty">尚无模型子代理 Token 记录。显式设置 TONMEN_AI_POOL 后，模型调用会按 Provider 分账。</div>`;
  }

  function renderRouting(hub) {
    const routes = hub.role_routes || {};
    const weights = hub.provider_weights || {};
    const routeHtml = Object.entries(routes).map(([role, route]) => `<div class="routing-item"><span>${esc(role.replaceAll("_", " "))}</span><code>${esc(route || "AUTO · weighted least usage")}</code></div>`).join("");
    const weightText = Object.entries(weights).map(([provider, weight]) => `${provider}=${weight}`).join(" · ") || "pool disabled";
    $("#routing-body").innerHTML = `<div class="routing-grid">${routeHtml}</div><div class="router-note">Pool: <code>${esc((hub.pool || []).join(", ") || "TONMEN_AI_POOL not set")}</code><br>Weights: <code>${esc(weightText)}</code><br>Global subagent token budget: <code>${esc(hub.token_budget || 0)}</code>. Stronger roles prefer capable providers; budget exhaustion and provider failures fall back to deterministic review.</div><div class="provider-secret-note">Secret values never enter this page. Browser-login credentials remain inside the official CLI credential store; API-key values are read only from server environment variables. Raw Evidence and Approval Tokens are not sent to Council providers.</div>`;
  }

  function bindProviderActions() {
    document.querySelectorAll("[data-provider-login]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const provider = button.dataset.providerLogin;
      try {
        busy = true;
        button.disabled = true;
        const result = await api(`/api/ai/providers/${encodeURIComponent(provider)}/login`, {method:"POST"});
        toast(`${result.label || provider}: 登录流程已启动`);
        await refresh();
      } catch (error) {
        toast(error.message || String(error), true);
      } finally {
        busy = false;
        button.disabled = false;
      }
    }));
    document.querySelectorAll("[data-provider-probe]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const provider = button.dataset.providerProbe;
      try {
        busy = true;
        button.disabled = true;
        const result = await api(`/api/ai/providers/${encodeURIComponent(provider)}/probe`, {method:"POST"});
        toast(`${provider}: ${result.detail}`, !result.ready);
        await refresh();
      } catch (error) {
        toast(error.message || String(error), true);
      } finally {
        busy = false;
        button.disabled = false;
      }
    }));
  }

  async function refresh() {
    try {
      alertBox("");
      const [lead, hub] = await Promise.all([api("/api/ai/lead"), api("/api/ai/providers")]);
      renderLead(lead);
      renderSummary(hub);
      renderProviders(hub);
      renderDistribution(hub);
      renderRouting(hub);
      bindProviderActions();
      $("#hub-updated").textContent = new Date().toLocaleTimeString();
    } catch (error) {
      alertBox(error.message || String(error));
    }
  }

  $("#hub-refresh")?.addEventListener("click", refresh);
  setInterval(() => { if (!document.hidden && !busy) refresh(); }, 5000);
  refresh();
})();
