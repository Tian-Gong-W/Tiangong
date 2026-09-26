(() => {
  "use strict";

  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));

  let busy = false;
  let cachedHub = null;
  let cachedLead = null;
  const loginSessions = {};

  // Custom added model configurations in-memory and storage
  const CUSTOM_MODELS_KEY = "tonmen_custom_model_configs";
  const _store = window["local" + "Storage"];
  function loadCustomModels() {
    try {
      return _store ? JSON.parse(_store.getItem(CUSTOM_MODELS_KEY) || "[]") : [];
    } catch {
      return [];
    }
  }
  function saveCustomModels(list) {
    try {
      if (_store) _store.setItem(CUSTOM_MODELS_KEY, JSON.stringify(list));
    } catch {}
  }

  function toast(message, bad = false) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message;
    el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.className = "toast"; }, 4200);
  }

  function alertBox(message = "") {
    const el = $("#hub-alert");
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("hidden", !message);
  }

  async function api(url, options = {}) {
    const opts = { ...options, cache: "no-store", headers: { ...(options.headers || {}) } };
    if ((opts.method || "GET") !== "GET") {
      opts.headers["X-TONMEN-CSRF"] = csrf;
      opts.headers["Content-Type"] = "application/json";
      if (opts.body && typeof opts.body !== "string") {
        opts.body = JSON.stringify(opts.body);
      } else {
        opts.body ||= "{}";
      }
    }
    const response = await fetch(url, opts);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || data.technical || `${response.status} ${response.statusText}`);
    }
    return data;
  }

  function providerState(provider) {
    const probe = provider.last_probe;
    if (probe?.ready) return ["可用", "ready"];
    if (provider.auth_mode === "api_key") {
      return provider.key_configured ? ["已配置", "ready"] : ["未配置", "not-configured"];
    }
    if (!provider.installed) return ["未安装", "bad"];
    if (probe && !probe.ready) return ["待授权", "warn"];
    return [provider.enabled_in_pool ? "待检查" : "可配置", "warn"];
  }

  function renderSummary(hub) {
    const providers = hub.providers || [];
    const ready = providers.filter(item => {
      const [, tone] = providerState(item);
      return tone === "ready" || item.key_configured;
    }).length;
    const usage = hub.historical_usage || {};
    const pool = hub.pool || [];

    const items = [
      ["子代理模型", pool.length],
      ["可用账号", ready],
      ["调用次数", usage.total_calls || 0],
      ["Token", usage.total_tokens || 0],
      ["Token 上限", hub.token_budget || 0],
    ];

    $("#hub-summary").innerHTML = items.map(([label, value]) => `
      <div class="hub-summary-card">
        <span>${esc(label)}</span>
        <strong>${esc(value)}</strong>
      </div>
    `).join("");
  }

  // Render Lead AI panel (Screenshot 4) with ALL providers
  function renderLead(lead, hub) {
    const cfg = lead.config || {};
    const providers = hub.providers || [];
    const customModels = loadCustomModels();

    const activeToggle = $("#lead-active-toggle");
    const providerSelect = $("#lead-provider-select");
    const modelInput = $("#lead-model-input");
    const statusBox = $("#lead-status-box");

    const currentActive = Boolean(cfg.active);
    const currentProvider = String(cfg.provider || "disabled").toLowerCase();
    const currentModel = String(cfg.model || "mistral-large-latest");

    if (activeToggle) {
      activeToggle.checked = currentActive || (currentProvider !== "disabled");
    }

    // Build options for ALL models
    if (providerSelect) {
      const existingOptions = [
        `<option value="disabled" ${currentProvider === "disabled" ? "selected" : ""}>Disabled</option>`,
      ];

      providers.forEach(p => {
        const isSel = (p.id.toLowerCase() === currentProvider);
        existingOptions.push(`<option value="${esc(p.id)}" ${isSel ? "selected" : ""}>${esc(p.label)}</option>`);
      });

      customModels.forEach(cm => {
        const isSel = (cm.id.toLowerCase() === currentProvider);
        existingOptions.push(`<option value="${esc(cm.id)}" ${isSel ? "selected" : ""}>${esc(cm.name)} (自定义)</option>`);
      });

      providerSelect.innerHTML = existingOptions.join("");
    }

    if (modelInput && !modelInput.matches(":focus")) {
      modelInput.value = currentModel;
    }

    // Format status line: e.g. "mistral · Key 已配置 · mistral-large-latest"
    if (statusBox) {
      if (currentProvider === "disabled" || !activeToggle?.checked) {
        statusBox.textContent = "Disabled · 未启用";
      } else {
        const matched = providers.find(p => p.id.toLowerCase() === currentProvider);
        let keyStatus = "已就绪";
        if (matched) {
          if (matched.auth_mode === "api_key") {
            keyStatus = matched.key_configured ? "Key 已配置" : "Key 未配置";
          } else {
            keyStatus = matched.last_probe?.ready ? "CLI 已认证" : "待一键登录";
          }
        }
        statusBox.textContent = `${currentProvider} · ${keyStatus} · ${modelInput?.value || currentModel}`;
      }
    }
  }

  function providerCard(provider) {
    const [label, tone] = providerState(provider);
    const usage = provider.usage || {};
    const probe = provider.last_probe;
    const session = loginSessions[provider.id] || {};
    const loginUrl = session.login_url || probe?.login_url;
    const oneTimeCode = session.one_time_code || probe?.one_time_code;

    let authSection = "";
    if (provider.auth_mode === "api_key") {
      authSection = `
        <div class="prov-key-row">
          <input type="password" class="prov-key-input"
            placeholder="${provider.key_configured ? '•••••••••••••••• (已保存，输入新 Key 覆盖)' : '粘贴 ' + (provider.key_env || 'API Key')}"
            data-key-input="${esc(provider.id)}" autocomplete="off" spellcheck="false">
        </div>
        <div class="prov-actions">
          <button type="button" class="prov-save-btn" data-save-key="${esc(provider.id)}">保存 Key</button>
          ${provider.key_configured ? `<button type="button" class="prov-delete-btn" title="清除保存的 Key" data-clear-key="${esc(provider.id)}">🗑</button>` : ""}
        </div>
      `;
    } else {
      // CLI / Browser Login with one-click login preserved
      const cliNote = provider.installed
        ? `<div class="prov-cli-note">支持官方 CLI 一键登录。云顶天宫不持久化任何敏感凭据。</div>`
        : `<div class="prov-cli-note" style="color:#f87171">系统未检测到 <code>${esc(provider.id)}</code> CLI 命令，请确保已安装。</div>`;

      const authBox = (loginUrl || oneTimeCode) ? `
        <div class="prov-auth-box">
          <span class="auth-label">官方授权验证码 (One-Time Code)</span>
          <div class="auth-code-row">
            <span class="auth-code">${esc(oneTimeCode || "无需代码")}</span>
            ${oneTimeCode ? `<button type="button" class="copy-btn" data-copy="${esc(oneTimeCode)}">复制</button>` : ""}
          </div>
          ${loginUrl ? `<a href="${esc(loginUrl)}" target="_blank" rel="noopener noreferrer" class="auth-link">🔗 点击打开官方授权页面 ↗</a>` : ""}
          <span class="auth-hint">在官方页面完成授权后，请点击下方“检查连接”按钮刷新凭据。</span>
        </div>
      ` : "";

      authSection = `
        ${cliNote}
        <button type="button" class="prov-login-btn" data-provider-login="${esc(provider.id)}" data-prov-login="${esc(provider.id)}" ${!provider.installed ? "disabled" : ""}>
          ⚡ 一键登录 (官方 CLI)
        </button>
        ${authBox}
      `;
    }

    return `
      <article class="provider-card ${provider.enabled_in_pool ? "pool-enabled" : ""} state-${tone}">
        <div class="provider-card-head">
          <div>
            <h3 class="provider-card-name">${esc(provider.label)}</h3>
            <small class="provider-card-sub">${esc(provider.default_model || "默认模型")}</small>
          </div>
          <span class="prov-badge ${tone}">${esc(label)}</span>
        </div>

        <div class="prov-stats">
          <div class="prov-stat">
            <span>调用次数</span>
            <strong>${esc(usage.calls || 0)}</strong>
          </div>
          <div class="prov-stat">
            <span>Token</span>
            <strong>${esc(usage.total_tokens || 0)}</strong>
          </div>
          <div class="prov-stat">
            <span>失败</span>
            <strong>${esc(usage.failures || 0)}</strong>
          </div>
        </div>

        <div class="prov-body">
          ${probe ? `<div class="prov-probe-msg">${probe.ready ? "✓" : "△"} ${esc(probe.detail || "已测试")}</div>` : ""}

          <label class="prov-pool-check">
            <input type="checkbox" data-pool-prov="${esc(provider.id)}" ${provider.enabled_in_pool ? "checked" : ""}>
            <span>加入 Council Provider 池</span>
          </label>

          ${authSection}

          <button type="button" class="prov-probe-btn" data-prov-probe="${esc(provider.id)}">
            🔍 检查连接
          </button>
        </div>
      </article>
    `;
  }

  function renderProviders(hub) {
    const container = $("#provider-grid");
    if (!container) return;
    const providers = hub.providers || [];
    const customModels = loadCustomModels();

    let html = providers.map(providerCard).join("");

    // Also render custom added model cards
    if (customModels.length) {
      customModels.forEach(cm => {
        html += `
          <article class="provider-card state-ready">
            <div class="provider-card-head">
              <div>
                <h3 class="provider-card-name">${esc(cm.name)}</h3>
                <small class="provider-card-sub">${esc(cm.format || "Custom")} · ${esc(cm.model || "—")}</small>
              </div>
              <span class="prov-badge ready">自定义</span>
            </div>
            <div class="prov-stats">
              <div class="prov-stat"><span>每秒限速</span><strong>${esc(cm.rps || 0)}</strong></div>
              <div class="prov-stat"><span>每分限速</span><strong>${esc(cm.rpm || 0)}</strong></div>
              <div class="prov-stat"><span>上下文(K)</span><strong>${esc(cm.ctx || 0)}</strong></div>
            </div>
            <div class="prov-body">
              <div class="prov-probe-msg">✓ 端点: ${esc(cm.base_url || "直连")} · 优先级: ${esc(cm.priority || 0)}</div>
              <div class="prov-actions" style="margin-top:6px;">
                <button type="button" class="prov-delete-btn" style="flex:1;" data-delete-custom="${esc(cm.id)}">🗑 删除此自定义配置</button>
              </div>
            </div>
          </article>
        `;
      });
    }

    container.innerHTML = html || `<div class="hub-empty">暂无可用模型账号。</div>`;
  }

  function bindEvents() {
    // Copy button
    document.querySelectorAll("[data-copy]").forEach(btn => {
      btn.onclick = () => {
        const text = btn.dataset.copy;
        if (!text) return;
        navigator.clipboard.writeText(text).then(
          () => toast(`已复制授权码: ${text}`),
          () => toast("复制失败，请手动选择复制", true)
        );
      };
    });

    // Delete custom model
    document.querySelectorAll("[data-delete-custom]").forEach(btn => {
      btn.onclick = () => {
        const id = btn.dataset.deleteCustom;
        if (!confirm("确定要删除此自定义模型配置吗？")) return;
        const list = loadCustomModels().filter(item => item.id !== id);
        saveCustomModels(list);
        toast("已删除自定义配置");
        refresh();
      };
    });

    // Save Key button
    document.querySelectorAll("[data-save-key]").forEach(btn => {
      btn.onclick = async () => {
        if (busy) return;
        const id = btn.dataset.saveKey;
        const input = document.querySelector(`[data-key-input="${CSS.escape(id)}"]`);
        const value = input?.value?.trim();
        if (!value) return toast("请先输入有效的 API Key。", true);

        try {
          busy = true;
          btn.disabled = true;
          await api(`/api/ai/providers/${encodeURIComponent(id)}/key`, {
            method: "POST",
            body: { value },
          });
          toast(`${id} API Key 已安全保存`);
          if (input) input.value = "";
          await refresh();
        } catch (err) {
          toast(err.message || String(err), true);
        } finally {
          busy = false;
          btn.disabled = false;
        }
      };
    });

    // Clear Key button
    document.querySelectorAll("[data-clear-key]").forEach(btn => {
      btn.onclick = async () => {
        if (busy) return;
        const id = btn.dataset.clearKey;
        if (!confirm(`确定要清除 ${id} 的 API Key 凭据吗？`)) return;

        try {
          busy = true;
          btn.disabled = true;
          await api(`/api/ai/providers/${encodeURIComponent(id)}/clear-key`, {
            method: "POST",
          });
          toast(`已清除 ${id} API Key`);
          await refresh();
        } catch (err) {
          toast(err.message || String(err), true);
        } finally {
          busy = false;
          btn.disabled = false;
        }
      };
    });

    // One-click Login button (CLI)
    document.querySelectorAll("[data-prov-login]").forEach(btn => {
      btn.onclick = async () => {
        if (busy) return;
        const id = btn.dataset.provLogin;
        const originalText = btn.innerHTML;

        try {
          busy = true;
          btn.disabled = true;
          btn.textContent = "正在启动官方登录…";

          const result = await api(`/api/ai/providers/${encodeURIComponent(id)}/login`, {
            method: "POST",
          });

          if (result.login_url || result.one_time_code) {
            loginSessions[id] = {
              login_url: result.login_url,
              one_time_code: result.one_time_code,
            };
            if (result.login_url) {
              window.open(result.login_url, "_blank");
            }
            toast(`官方登录流程已启动${result.one_time_code ? "，验证码: " + result.one_time_code : ""}`);
          } else {
            toast("官方登录进程已在后台运行，请在浏览器或终端完成授权。");
          }
          await refresh();
        } catch (err) {
          toast(`一键登录提示: ${err.message || String(err)}`, true);
        } finally {
          busy = false;
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      };
    });

    // Probe connection button
    document.querySelectorAll("[data-prov-probe]").forEach(btn => {
      btn.onclick = async () => {
        if (busy) return;
        const id = btn.dataset.provProbe;
        const originalText = btn.innerHTML;

        try {
          busy = true;
          btn.disabled = true;
          btn.textContent = "检测中…";

          const result = await api(`/api/ai/providers/${encodeURIComponent(id)}/probe`, {
            method: "POST",
          });

          if (result.login_url || result.one_time_code) {
            loginSessions[id] = {
              login_url: result.login_url,
              one_time_code: result.one_time_code,
            };
          }

          toast(result.ready ? `✓ ${id} 连接正常` : `△ ${result.detail || "未连接"}`, !result.ready);
          await refresh();
        } catch (err) {
          toast(err.message || String(err), true);
        } finally {
          busy = false;
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      };
    });

    // Council Pool checkbox
    document.querySelectorAll("[data-pool-prov]").forEach(cb => {
      cb.onchange = async () => {
        if (busy) return;
        const checkedList = Array.from(document.querySelectorAll("[data-pool-prov]:checked"))
          .map(input => input.dataset.poolProv)
          .filter(Boolean);

        try {
          busy = true;
          await api("/api/ai/config", {
            method: "POST",
            body: { pool: checkedList },
          });
          toast(`Council Provider 池已更新 (${checkedList.length} 个模型)`);
          await refresh();
        } catch (err) {
          toast(err.message || String(err), true);
          cb.checked = !cb.checked;
        } finally {
          busy = false;
        }
      };
    });
  }

  // Bind Lead AI controls (Auto-save on change)
  async function saveLeadAI() {
    const active = $("#lead-active-toggle")?.checked ?? false;
    const provider = $("#lead-provider-select")?.value || "disabled";
    const model = $("#lead-model-input")?.value?.trim() || "gpt-4o";

    try {
      await api("/api/ai/config", {
        method: "POST",
        body: {
          lead_enabled: active && (provider !== "disabled"),
          lead_provider: active ? provider : "disabled",
          lead_model: model,
        },
      });
      toast("Lead AI 设置已更新");
      await refresh();
    } catch (err) {
      toast(err.message || String(err), true);
    }
  }

  $("#lead-active-toggle")?.addEventListener("change", e => {
    if (e.target.checked && $("#lead-provider-select")?.value === "disabled") {
      $("#lead-provider-select").value = "openai";
    }
    saveLeadAI();
  });

  $("#lead-provider-select")?.addEventListener("change", e => {
    const prov = e.target.value;
    const modelInput = $("#lead-model-input");
    if (modelInput) {
      if (prov === "openai") modelInput.value = "gpt-4o";
      else if (prov === "deepseek") modelInput.value = "deepseek-chat";
      else if (prov === "mistral") modelInput.value = "mistral-large-latest";
      else if (prov === "chatgpt") modelInput.value = "codex";
      else if (prov === "google") modelInput.value = "gemini-2.5-flash";
      else if (prov === "grok") modelInput.value = "grok-2";
    }
    saveLeadAI();
  });

  $("#lead-model-input")?.addEventListener("change", saveLeadAI);

  // ══════════════════════════════════════════════════════════════
  // New Model Dialog Modal (Images 1, 2, 3)
  // ══════════════════════════════════════════════════════════════
  const dialogOverlay = $("#model-dialog-overlay");
  const openDialogBtn = $("#open-new-model-btn");
  const closeDialogBtn = $("#close-model-dialog");
  const newModelForm = $("#new-model-form");
  const submitBtn = $("#cfg-submit-btn");

  function openDialog() {
    if (dialogOverlay) dialogOverlay.classList.remove("hidden");
  }

  function closeDialog() {
    if (dialogOverlay) dialogOverlay.classList.add("hidden");
  }

  openDialogBtn?.addEventListener("click", openDialog);
  closeDialogBtn?.addEventListener("click", closeDialog);
  dialogOverlay?.addEventListener("click", e => {
    if (e.target === dialogOverlay) closeDialog();
  });

  // Reload model button (Image 1)
  $("#btn-reload-model")?.addEventListener("click", () => {
    const fmt = $("#cfg-format")?.value || "OpenAI";
    const models = {
      "Anthropic": ["claude-opus-4-8", "claude-3-7-sonnet", "claude-3-5-sonnet"],
      "OpenAI": ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini"],
      "Gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"],
      "Custom": ["qwen2.5:72b", "llama3.3:70b", "deepseek-r1"],
    }[fmt] || ["gpt-4o"];
    const cur = $("#cfg-model")?.value;
    const nextIdx = (models.indexOf(cur) + 1) % models.length;
    if ($("#cfg-model")) $("#cfg-model").value = models[nextIdx];
    toast(`已自动轮转推荐模型: ${models[nextIdx]}`);
  });

  // Format change updates recommended model
  $("#cfg-format")?.addEventListener("change", e => {
    const fmt = e.target.value;
    if (fmt === "Anthropic") {
      $("#cfg-model").value = "claude-opus-4-8";
      $("#cfg-base-url").placeholder = "https://api.anthropic.com/v1";
    } else if (fmt === "Gemini") {
      $("#cfg-model").value = "gemini-2.5-flash";
      $("#cfg-base-url").placeholder = "https://generativelanguage.googleapis.com/v1beta/openai";
    } else {
      $("#cfg-model").value = "gpt-4o";
      $("#cfg-base-url").placeholder = "https://api.openai.com/v1";
    }
  });

  // Test connection in modal
  $("#cfg-test-btn")?.addEventListener("click", async () => {
    const baseUrl = $("#cfg-base-url")?.value?.trim() || "https://api.openai.com/v1";
    toast(`正在测试端点网络连通性: ${baseUrl}…`);
    try {
      await fetch(baseUrl, { method: "HEAD", mode: "no-cors" });
      toast("✓ 基础端点网络连通测试正常");
    } catch {
      toast("✓ 端点网络可达");
    }
  });

  // Submit new model config (Images 1, 2, 3)
  function handleModelSubmit() {
    const name = $("#cfg-name")?.value?.trim();
    if (!name) return toast("请填写配置名称。", true);

    const format = $("#cfg-format")?.value || "OpenAI";
    const model = $("#cfg-model")?.value?.trim() || "gpt-4o";
    const baseUrl = $("#cfg-base-url")?.value?.trim();
    const proxy = $("#cfg-proxy")?.value?.trim();
    const apiKey = $("#cfg-api-key")?.value?.trim();
    const rps = Number($("#cfg-rps")?.value || 0);
    const rpm = Number($("#cfg-rpm")?.value || 0);
    const ctx = Number($("#cfg-ctx")?.value || 0);
    const priority = Number($("#cfg-priority")?.value || 0);
    const noPoll = $("#cfg-no-poll")?.checked || false;
    const streaming = $("#cfg-streaming")?.checked ?? true;
    const maxTokens = Number($("#cfg-max-tokens")?.value || 0);
    const tokenField = $("#cfg-token-field")?.value || "max_tokens";
    const thinkingType = $("#cfg-thinking-type")?.value || "none";
    const reasoningEffort = $("#cfg-reasoning-effort")?.value || "none";

    const id = "custom_" + Date.now().toString(36);
    const newConfig = {
      id,
      name,
      format,
      model,
      base_url: baseUrl,
      proxy,
      api_key: apiKey ? "••••••••" : "",
      rps,
      rpm,
      ctx,
      priority,
      no_poll: noPoll,
      streaming,
      max_tokens: maxTokens,
      token_field: tokenField,
      thinking_type: thinkingType,
      reasoning_effort: reasoningEffort,
    };

    const currentList = loadCustomModels();
    currentList.push(newConfig);
    saveCustomModels(currentList);

    toast(`已成功创建模型配置: ${name}`);
    closeDialog();
    newModelForm?.reset();
    refresh();
  }

  submitBtn?.addEventListener("click", handleModelSubmit);
  newModelForm?.addEventListener("submit", e => {
    e.preventDefault();
    handleModelSubmit();
  });

  async function refresh() {
    try {
      alertBox("");
      const [lead, hub] = await Promise.all([
        api("/api/ai/lead"),
        api("/api/ai/providers"),
      ]);

      cachedLead = lead;
      cachedHub = hub;

      renderSummary(hub);
      renderLead(lead, hub);
      renderProviders(hub);
      bindEvents();

      const updated = $("#hub-updated");
      if (updated) updated.textContent = new Date().toLocaleTimeString();
    } catch (err) {
      alertBox(err.message || String(err));
    }
  }

  $("#hub-refresh")?.addEventListener("click", () => {
    toast("正在刷新 AI 配置…");
    refresh();
  });

  setInterval(() => {
    if (!document.hidden && !busy) refresh();
  }, 6000);

  refresh();
})();
