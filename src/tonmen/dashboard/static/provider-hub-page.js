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
    if (probe?.ready) return ["可用", "ready"];
    if (provider.auth_mode === "api_key") return provider.key_configured ? ["已配置", "ready"] : ["未配置", "bad"];
    if (!provider.installed) return ["未安装", "bad"];
    if (probe && !probe.ready) return ["需登录", "warn"];
    return [provider.enabled_in_pool ? "待检查" : "可配置", "warn"];
  }

  function renderSummary(hub) {
    const providers = hub.providers || [];
    const ready = providers.filter(item => providerState(item)[1] === "ready").length;
    const usage = hub.historical_usage || {};
    const pool = hub.pool || [];
    const html = [
      ["子代理模型", pool.length],
      ["可用账号", ready],
      ["调用次数", usage.total_calls || 0],
      ["Token", usage.total_tokens || 0],
      ["Token 上限", hub.token_budget || 0],
    ].map(([label, value]) => `<div class="hub-summary-card"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
    $("#hub-summary").innerHTML = html;
    $("#pool-state").textContent = pool.length ? `${pool.length} 个已启用` : "未启用";
    $("#pool-state").className = `module-badge ${pool.length ? "ok" : "blue"}`;
    $("#token-total").textContent = `${usage.total_tokens || 0}`;
  }

  function renderLead(data) {
    const cfg = data.config || {};
    const current = data.current;
    const state = $("#lead-state");
    const body = $("#lead-body");
    const active = Boolean(cfg.active);
    state.textContent = active ? "已开启" : cfg.provider && cfg.provider !== "disabled" ? "降级模式" : "未开启";
    state.className = `module-badge ${active ? "ok" : cfg.provider && cfg.provider !== "disabled" ? "warn" : "blue"}`;
    if (!current) {
      body.innerHTML = `<div class="lead-runtime"><div><span>服务</span><strong>${esc(cfg.provider || "未启用")}</strong></div><div><span>模型</span><strong>${esc(cfg.model || "—")}</strong></div><div><span>账号</span><strong>${cfg.key_configured ? "已配置" : "未配置"}</strong></div></div><div class="hub-empty">暂无 AI 主控记录。</div>`;
      return;
    }
    const md = current.latest_directive?.metadata || {};
    const telemetry = current.telemetry || {};
    body.innerHTML = `<div class="lead-runtime"><div><span>模型</span><strong>${esc(md.provider || cfg.provider || "规则模式")} · ${esc(md.model || cfg.model || "—")}</strong></div><div><span>进度</span><strong>${esc(current.rounds_completed || 0)} / ${esc(current.target_rounds || 8)}</strong></div><div><span>Token</span><strong>${esc(telemetry.total_tokens || 0)}</strong></div></div><div class="lead-directive"><h3>${esc(md.focus || "当前判断")}</h3><p>${esc(md.objective || "—")}</p><code>${esc(md.recommended_action || "—")} · 置信度 ${esc(md.confidence ?? "—")}</code>${md.error ? `<p>${esc(md.error)}</p>` : ""}</div>`;
  }

  function providerCard(provider) {
    const [label, tone] = providerState(provider);
    const usage = provider.usage || {};
    const loginButton = provider.auth_mode === "browser_login" && provider.installed ? `<button class="primary" type="button" data-provider-login="${esc(provider.id)}">登录</button>` : "";
    const authValue = provider.auth_mode === "api_key" ? (provider.key_configured ? "已配置" : "未配置") : (provider.installed ? "已安装" : "未安装");
    const probe = provider.last_probe;
    return `<article class="provider-card ${provider.enabled_in_pool ? "pool-enabled" : ""}"><div class="provider-card-head"><div><h3>${esc(provider.label)}<small>${esc(provider.default_model || "默认模型")}</small></h3></div><span class="provider-state ${tone}">${esc(label)}</span></div><div class="provider-meta"><span>子代理</span><strong>${provider.enabled_in_pool ? "启用" : "关闭"}</strong><span>账号</span><strong>${esc(authValue)}</strong><span>权重</span><strong>${esc(provider.cost_weight ?? "—")}</strong></div><div class="provider-usage"><span>调用 <b>${esc(usage.calls || 0)}</b></span><span>Token <b>${esc(usage.total_tokens || 0)}</b></span><span>失败 <b>${esc(usage.failures || 0)}</b></span></div><div class="provider-actions">${loginButton}<button class="ghost" type="button" data-provider-probe="${esc(provider.id)}">检查</button></div>${probe ? `<div class="provider-probe">${probe.ready ? "✓" : "△"} ${esc(probe.detail || "")}</div>` : ""}</article>`;
  }

  function renderProviders(hub) {
    $("#provider-grid").innerHTML = (hub.providers || []).map(providerCard).join("") || `<div class="hub-empty">暂无模型账号。</div>`;
  }

  function renderDistribution(hub) {
    const rows = (hub.distribution || []).filter(item => item.calls || item.tokens);
    $("#distribution-list").innerHTML = rows.length ? rows.map(item => `<div class="distribution-row"><strong>${esc(item.provider)}</strong><progress max="100" value="${Math.max(0, Math.min(100, Number(item.token_share_percent) || 0))}"></progress><span>${esc(item.token_share_percent)}% · ${esc(item.tokens)} Token · ${esc(item.calls)} 次</span></div>`).join("") : `<div class="hub-empty">暂无调用记录。</div>`;
  }

  function renderRouting(hub) {
    const routes = hub.role_routes || {};
    const weights = hub.provider_weights || {};
    const routeHtml = Object.entries(routes).map(([role, route]) => `<div class="routing-item"><span>${esc(role.replaceAll("_", " "))}</span><code>${esc(route || "自动")}</code></div>`).join("");
    const weightText = Object.entries(weights).map(([provider, weight]) => `${provider}=${weight}`).join(" · ") || "未启用";
    $("#routing-body").innerHTML = `<div class="routing-grid">${routeHtml}</div><div class="router-note">子代理模型：<code>${esc((hub.pool || []).join(", ") || "未启用")}</code><br>权重：<code>${esc(weightText)}</code><br>Token 上限：<code>${esc(hub.token_budget || 0)}</code></div><div class="provider-secret-note">Key 不会显示在页面、任务记录或报告中。AI 不能执行工具或自行审批。</div>`;
  }

  function bindProviderActions() {
    document.querySelectorAll("[data-provider-login]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const provider = button.dataset.providerLogin;
      try { busy = true; button.disabled = true; await api(`/api/ai/providers/${encodeURIComponent(provider)}/login`, {method:"POST"}); toast("已打开登录流程"); await refresh(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));
    document.querySelectorAll("[data-provider-probe]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const provider = button.dataset.providerProbe;
      try { busy = true; button.disabled = true; const result = await api(`/api/ai/providers/${encodeURIComponent(provider)}/probe`, {method:"POST"}); toast(result.ready ? "连接正常" : result.detail, !result.ready); await refresh(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));
  }

  async function refresh() {
    try {
      alertBox("");
      const [lead, hub] = await Promise.all([api("/api/ai/lead"), api("/api/ai/providers")]);
      renderLead(lead); renderSummary(hub); renderProviders(hub); renderDistribution(hub); renderRouting(hub); bindProviderActions();
      $("#hub-updated").textContent = new Date().toLocaleTimeString();
    } catch (error) { alertBox(error.message || String(error)); }
  }

  $("#hub-refresh")?.addEventListener("click", refresh);
  setInterval(() => { if (!document.hidden && !busy) refresh(); }, 5000);
  refresh();
})();
