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
    document.getElementById("hub-alert")?.insertAdjacentElement("afterend", root);
    return root;
  }

  function providerSetup(provider) {
    if (provider.auth_mode === "api_key") {
      const ready = Boolean(provider.key_configured);
      return `<article class="easy-provider ${ready ? "ready" : ""}">
        <div><strong>${esc(provider.label)}</strong><small>${ready ? "已配置" : "未配置"}</small></div>
        <div class="easy-key-row"><input type="password" autocomplete="off" spellcheck="false" placeholder="粘贴 API Key" data-easy-key="${esc(provider.id)}"><button type="button" class="primary" data-easy-save-key="${esc(provider.id)}">保存</button>${provider.local_secret?.persisted_by_tonmen ? `<button type="button" class="ghost" data-easy-clear-key="${esc(provider.id)}">清除</button>` : ""}</div>
      </article>`;
    }
    const command = (provider.login_command || []).join(" ");
    return `<article class="easy-provider ${provider.installed ? "ready" : ""}">
      <div><strong>${esc(provider.label)}</strong><small>${provider.installed ? "可登录" : "需安装官方 CLI"}</small></div>
      ${command ? `<code>${esc(command)}</code>` : ""}
      <div class="easy-actions">${provider.installed ? `<button type="button" class="primary" data-easy-login="${esc(provider.id)}">登录</button>` : ""}<button type="button" class="ghost" data-easy-probe="${esc(provider.id)}">检查</button></div>
    </article>`;
  }

  function render(lead, hub) {
    const root = ensureRoot();
    const cfg = lead.config || {};
    const pool = hub.pool || [];
    const providers = hub.providers || [];
    const readyCount = providers.filter(item => item.key_configured || item.last_probe?.ready).length;
    const overrides = hub.configuration_precedence?.explicit_setting_envs || [];
    root.innerHTML = `<div class="easy-head"><div><h2>AI 快速配置</h2><p>配置账号，然后开启主控和子代理。</p></div><div class="easy-status"><b>${cfg.active ? "主控已开启" : "主控未开启"}</b><span>${pool.length ? "子代理已开启" : "子代理未开启"}</span></div></div>
      ${overrides.length ? `<div class="easy-warning">服务器环境变量正在覆盖网页设置。</div>` : ""}
      <div class="easy-steps"><div><b>1</b><strong>模型账号</strong><span>${readyCount} 个可用</span></div><div><b>2</b><strong>AI 主控</strong><span>${cfg.provider === "openai" ? "已开启" : "未开启"}</span><button type="button" class="${cfg.provider === "openai" ? "ghost" : "primary"}" data-easy-lead="${cfg.provider === "openai" ? "off" : "on"}">${cfg.provider === "openai" ? "关闭" : "开启"}</button></div><div><b>3</b><strong>子代理</strong><span>${pool.length ? "已开启" : "未开启"}</span><button type="button" class="${pool.length ? "ghost" : "primary"}" data-easy-pool="${pool.length ? "off" : "auto"}">${pool.length ? "关闭" : "自动开启"}</button></div></div>
      <div class="easy-provider-grid">${providers.map(providerSetup).join("")}</div>
      <div class="easy-footer"><span>AI 只做分析，不会自行执行或审批。</span><button type="button" class="ghost" data-easy-advanced>高级信息</button></div>`;
    bind();
  }

  function bind() {
    document.querySelectorAll("[data-easy-save-key]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const id = button.dataset.easySaveKey;
      const input = document.querySelector(`[data-easy-key="${CSS.escape(id)}"]`);
      const value = input?.value?.trim();
      if (!value) return toast("请先粘贴 API Key。", true);
      try {
        busy = true; button.disabled = true;
        await api(`/api/ai/providers/${encodeURIComponent(id)}/key`, {method:"POST", body:{value}});
        if (input) input.value = "";
        toast("已保存");
        await refresh(); document.getElementById("hub-refresh")?.click();
      } catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));

    document.querySelectorAll("[data-easy-clear-key]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const id = button.dataset.easyClearKey;
      try {
        busy = true; button.disabled = true;
        const result = await api(`/api/ai/providers/${encodeURIComponent(id)}/clear-key`, {method:"POST"});
        toast(result.environment_override ? "本机保存值已清除，服务器配置仍生效。" : "已清除");
        await refresh(); document.getElementById("hub-refresh")?.click();
      } catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));

    document.querySelectorAll("[data-easy-login]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const id = button.dataset.easyLogin;
      try { busy = true; button.disabled = true; await api(`/api/ai/providers/${encodeURIComponent(id)}/login`, {method:"POST"}); toast("已打开登录流程"); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));

    document.querySelectorAll("[data-easy-probe]").forEach(button => button.addEventListener("click", async () => {
      if (busy) return;
      const id = button.dataset.easyProbe;
      try {
        busy = true; button.disabled = true;
        const result = await api(`/api/ai/providers/${encodeURIComponent(id)}/probe`, {method:"POST"});
        toast(result.ready ? "连接正常" : result.detail, !result.ready);
        await refresh();
      } catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; button.disabled = false; }
    }));

    document.querySelector("[data-easy-lead]")?.addEventListener("click", async event => {
      if (busy) return;
      const enabled = event.currentTarget.dataset.easyLead === "on";
      try { busy = true; await api("/api/ai/config", {method:"POST", body:{lead_enabled:enabled}}); toast(enabled ? "AI 主控已开启" : "AI 主控已关闭"); await refresh(); document.getElementById("hub-refresh")?.click(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; }
    });

    document.querySelector("[data-easy-pool]")?.addEventListener("click", async event => {
      if (busy) return;
      const enabled = event.currentTarget.dataset.easyPool === "auto";
      try { busy = true; await api("/api/ai/config", {method:"POST", body:{pool:enabled ? ["auto"] : []}}); toast(enabled ? "子代理已自动开启" : "子代理已关闭"); await refresh(); document.getElementById("hub-refresh")?.click(); }
      catch (error) { toast(error.message || String(error), true); }
      finally { busy = false; }
    });

    document.querySelector("[data-easy-advanced]")?.addEventListener("click", event => {
      const page = document.querySelector(".provider-page");
      const show = !page?.classList.contains("show-advanced");
      page?.classList.toggle("show-advanced", show);
      event.currentTarget.textContent = show ? "收起高级信息" : "高级信息";
    });
  }

  async function refresh() {
    try {
      const [lead, hub] = await Promise.all([api("/api/ai/lead"), api("/api/ai/providers")]);
      render(lead, hub);
    } catch (error) {
      ensureRoot().innerHTML = `<div class="easy-warning">${esc(error.message || error)}</div>`;
    }
  }
  refresh();
})();
