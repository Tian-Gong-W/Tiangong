(() => {
  "use strict";
  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  let busy = false;

  async function api(url, options = {}) {
    const opts = {...options, cache:"no-store", headers:{...(options.headers || {})}};
    if ((opts.method || "GET") !== "GET") {
      opts.headers["X-TONMEN-CSRF"] = csrf;
      opts.headers["Content-Type"] = "application/json";
      if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
      else opts.body ||= "{}";
    }
    const response = await fetch(url, opts);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data;
  }

  function toast(message, bad = false) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.t); toast.t = setTimeout(() => { el.className = "toast"; }, 4200);
  }

  function ensureRoot() {
    let root = document.getElementById("easy-ai-setup");
    if (root) return root;
    root = document.createElement("section");
    root.id = "easy-ai-setup";
    root.className = "easy-ai-setup";
    const alert = document.getElementById("hub-alert");
    alert?.insertAdjacentElement("afterend", root);
    return root;
  }

  function providerSetup(provider) {
    const status = provider.local_secret || {};
    if (provider.auth_mode === "api_key") {
      const source = provider.secret_env_overrides_local ? "服务器环境变量优先" : status.source === "local_store" ? "已安全保存到本机" : provider.key_configured ? "已配置" : "未配置";
      return `<article class="easy-provider ${provider.key_configured ? "ready" : ""}">
        <div><strong>${esc(provider.label)}</strong><small>${esc(provider.default_model || "provider default")} · ${esc(source)}</small></div>
        <div class="easy-key-row"><input type="password" autocomplete="off" spellcheck="false" placeholder="粘贴 ${esc(provider.label)} API Key" data-easy-key="${esc(provider.id)}"><button type="button" class="primary" data-easy-save-key="${esc(provider.id)}">保存 Key</button>${provider.local_secret?.persisted_by_tonmen ? `<button type="button" class="ghost" data-easy-clear-key="${esc(provider.id)}">清除</button>` : ""}</div>
        <p>Key 只保存在运行 TONMEN 的这台机器上，页面不会回显 Key 内容。</p>
      </article>`;
    }
    const command = (provider.login_command || []).join(" ");
    return `<article class="easy-provider ${provider.installed ? "ready" : ""}">
      <div><strong>${esc(provider.label)}</strong><small>${provider.installed ? "官方 CLI 已安装" : "官方 CLI 未安装"}</small></div>
      <p>${esc(provider.setup_hint || "安装官方 CLI 后即可使用网页登录。")}</p>
      ${command ? `<code>${esc(command)}</code>` : ""}
      <div class="easy-actions">${provider.installed ? `<button type="button" class="primary" data-easy-login="${esc(provider.id)}">网页登录</button>` : ""}<button type="button" class="ghost" data-easy-probe="${esc(provider.id)}">检查连接</button></div>
    </article>`;
  }

  function render(lead, hub) {
    const root = ensureRoot();
    const cfg = lead.config || {};
    const settings = hub.local_settings || {};
    const pool = hub.pool || [];
    const providers = hub.providers || [];
    const readyCount = providers.filter(item => item.key_configured || item.last_probe?.ready).length;
    const overrides = hub.configuration_precedence?.explicit_setting_envs || [];
    root.innerHTML = `<div class="easy-head"><div><span>3 步完成 AI 配置</span><h2>快速开始 / Easy Setup</h2><p>不用手动 export 环境变量：先配置一个模型账号，再开启 AI 主控与子代理池。</p></div><div class="easy-status"><b>${cfg.active ? "AI 主控运行中" : cfg.provider === "openai" ? "AI 主控待 Key" : "AI 主控未启用"}</b><span>${pool.length ? `Council: ${esc(pool.join(", "))}` : "Council: 安全降级模式"}</span></div></div>
      ${overrides.length ? `<div class="easy-warning">当前进程存在环境变量覆盖：${esc(overrides.join(", "))}。网页设置会保存，但这些环境变量仍优先。</div>` : ""}
      <div class="easy-steps"><div><b>1</b><strong>配置模型账号</strong><span>${readyCount} 个 Provider 已可用/已配置</span></div><div><b>2</b><strong>开启 AI 主控</strong><span>负责每轮目标与综合判断</span><button type="button" class="${cfg.provider === "openai" ? "ghost" : "primary"}" data-easy-lead="${cfg.provider === "openai" ? "off" : "on"}">${cfg.provider === "openai" ? "关闭 AI 主控" : "启用 AI 主控"}</button></div><div><b>3</b><strong>开启子代理协作</strong><span>自动使用当前可用 Provider 分担 Council</span><button type="button" class="${pool.length ? "ghost" : "primary"}" data-easy-pool="${pool.length ? "off" : "auto"}">${pool.length ? "关闭模型子代理" : "自动启用可用 Provider"}</button></div></div>
      <div class="easy-provider-grid">${providers.map(providerSetup).join("")}</div>
      <div class="easy-note">AI 只负责分析与建议；Scope、主动扫描审批和工具执行权限仍由 TONMEN 治理层控制。</div>`;
    bind();
  }

  function bind() {
    document.querySelectorAll("[data-easy-save-key]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return; const id = button.dataset.easySaveKey; const input = document.querySelector(`[data-easy-key="${CSS.escape(id)}"]`); const value = input?.value?.trim();
      if (!value) return toast("请先粘贴 API Key。", true);
      try { busy = true; button.disabled = true; await api(`/api/ai/providers/${encodeURIComponent(id)}/key`, {method:"POST", body:{value}}); if (input) input.value = ""; toast(`${id}: Key 已安全保存`); await refresh(); document.getElementById("hub-refresh")?.click(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));
    document.querySelectorAll("[data-easy-clear-key]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return; const id = button.dataset.easyClearKey;
      try { busy = true; button.disabled = true; const result = await api(`/api/ai/providers/${encodeURIComponent(id)}/clear-key`, {method:"POST"}); toast(result.environment_override ? "本机保存值已清除，但服务器环境变量仍在生效。" : `${id}: Key 已清除`); await refresh(); document.getElementById("hub-refresh")?.click(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));
    document.querySelectorAll("[data-easy-login]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return; const id = button.dataset.easyLogin;
      try { busy = true; button.disabled = true; await api(`/api/ai/providers/${encodeURIComponent(id)}/login`, {method:"POST"}); toast(`${id}: 已启动官方登录流程`); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));
    document.querySelectorAll("[data-easy-probe]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return; const id = button.dataset.easyProbe;
      try { busy = true; button.disabled = true; const result = await api(`/api/ai/providers/${encodeURIComponent(id)}/probe`, {method:"POST"}); toast(result.ready ? `${id}: 连接正常` : `${id}: ${result.detail}`, !result.ready); await refresh(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));
    document.querySelector("[data-easy-lead]")?.addEventListener("click", async event => {
      if (busy) return; const enabled = event.currentTarget.dataset.easyLead === "on";
      try { busy = true; await api("/api/ai/config", {method:"POST", body:{lead_enabled:enabled}}); toast(enabled ? "AI 主控已启用；若 OpenAI Key 已配置将立即使用模型。" : "AI 主控已关闭，任务会使用确定性降级。" ); await refresh(); document.getElementById("hub-refresh")?.click(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; }
    });
    document.querySelector("[data-easy-pool]")?.addEventListener("click", async event => {
      if (busy) return; const mode = event.currentTarget.dataset.easyPool; const pool = mode === "auto" ? ["auto"] : [];
      try { busy = true; await api("/api/ai/config", {method:"POST", body:{pool}}); toast(mode === "auto" ? "模型子代理池已设为自动：只选择当前可用 Provider。" : "模型子代理已关闭，Council 使用安全降级模式。" ); await refresh(); document.getElementById("hub-refresh")?.click(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; }
    });
  }

  async function refresh() {
    try { const [lead, hub] = await Promise.all([api("/api/ai/lead"), api("/api/ai/providers")]); render(lead, hub); }
    catch (error) { ensureRoot().innerHTML = `<div class="easy-warning">${esc(error.message || error)}</div>`; }
  }
  refresh();
})();
