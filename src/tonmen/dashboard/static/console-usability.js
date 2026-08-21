(() => {
  "use strict";
  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const plainNames = {
    "天域":"授权范围", "天律":"安全策略", "天工":"工具", "天役":"执行节点",
    "天鑑":"情报", "天策":"AI 推理", "主導":"AI 主控", "天衡":"任务循环",
    "天冊":"任务记录", "審批":"人工确认", "設定":"设置"
  };
  const states = {
    waiting_approval:"等待批准", succeeded:"已完成", skipped:"已跳过", denied:"已拒绝",
    failed:"失败", running:"执行中", pending:"等待执行"
  };

  function toast(message, bad = false) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.t); toast.t = setTimeout(() => { el.className = "toast"; }, 4200);
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

  function simplifyLanguage() {
    document.querySelectorAll(".nav-item b").forEach(node => {
      const label = node.childNodes[0]?.textContent?.trim() || node.textContent.trim();
      const plain = plainNames[label];
      if (!plain || node.querySelector(".plain-nav-name")) return;
      const small = document.createElement("small");
      small.className = "plain-nav-name";
      small.textContent = ` · ${plain}`;
      node.appendChild(small);
    });
    document.querySelectorAll(".step-state").forEach(node => {
      const state = [...node.classList].find(name => states[name]);
      if (state) node.textContent = states[state];
    });
    const pill = document.getElementById("mission-state");
    if (pill) {
      const state = [...pill.classList].find(name => states[name]);
      if (state) pill.textContent = states[state];
    }
    document.querySelectorAll("#approve-btn,.deck-approve,[data-approve-run]").forEach(button => {
      if (!button.dataset.easyLabel) {
        button.dataset.easyLabel = "1";
        if (!button.disabled) button.textContent = "继续主动验证";
      }
    });
  }

  function runIdFor(button) {
    if (button.dataset.approveRun) return button.dataset.approveRun;
    const selected = document.getElementById("mission-select")?.value;
    return selected || new URLSearchParams(location.search).get("run") || null;
  }

  async function pollApproval(runId) {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, attempt < 5 ? 1000 : 2500));
      try {
        const status = await api(`/api/missions/${encodeURIComponent(runId)}/approval-status`);
        document.getElementById("refresh-btn")?.click();
        document.querySelector("[data-module-refresh]")?.click();
        if (status.status === "completed") {
          toast(status.message || "主动验证已完成。");
          return;
        }
        if (status.status === "failed") {
          toast(status.message || "主动验证未完成，请查看任务状态。", true);
          return;
        }
      } catch (_) { return; }
    }
  }

  async function approve(button) {
    const runId = runIdFor(button);
    if (!runId) return toast("请先选择一个等待批准的任务。", true);
    const now = Date.now();
    const until = Number(button.dataset.confirmUntil || 0);
    if (now > until) {
      button.dataset.confirmUntil = String(now + 8000);
      button.textContent = "再次点击确认主动扫描";
      button.classList.add("easy-confirm");
      toast("这一步会向已授权目标发起主动验证。请在 8 秒内再次点击确认。", false);
      setTimeout(() => {
        if (Date.now() > Number(button.dataset.confirmUntil || 0)) {
          button.textContent = "继续主动验证";
          button.classList.remove("easy-confirm");
        }
      }, 8200);
      return;
    }
    button.disabled = true;
    button.textContent = "已受理，后台执行中…";
    try {
      const result = await api(`/api/missions/${encodeURIComponent(runId)}/approve`, {method:"POST"});
      toast(result.message || "已受理，后台正在执行主动验证。你可以继续使用页面。");
      pollApproval(runId);
    } catch (error) {
      button.disabled = false;
      button.textContent = "继续主动验证";
      toast(error.message || String(error), true);
    }
  }

  document.addEventListener("click", event => {
    const button = event.target.closest?.("#approve-btn,.deck-approve,[data-approve-run]");
    if (!button || button.disabled) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    approve(button);
  }, true);

  const observer = new MutationObserver(simplifyLanguage);
  observer.observe(document.documentElement, {childList:true, subtree:true});
  simplifyLanguage();
})();
