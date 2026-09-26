(() => {
  "use strict";

  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const terminalLabels = new Set(["完成", "失败", "拒绝"]);

  function toast(message, bad = false) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.className = `toast show${bad ? " error" : ""}`;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.className = "toast"; }, 3200);
  }

  async function post(url) {
    const response = await fetch(url, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-TONMEN-CSRF": csrf,
      },
      body: "{}",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `${response.status} ${response.statusText}`);
    return payload;
  }

  function selectedRow() {
    return document.querySelector("#module-page-root .module-table tbody tr.selected[data-select-run]");
  }

  function selectedRun() {
    return new URLSearchParams(location.search).get("run") || selectedRow()?.dataset.selectRun || null;
  }

  function selectedStateLabel() {
    return selectedRow()?.querySelector(".module-badge")?.textContent?.trim() || "";
  }

  function refreshMissions(clearRun = false) {
    if (clearRun) history.replaceState({}, "", "/missions");
    const refresh = document.querySelector("#module-page-root [data-module-refresh]");
    if (refresh) refresh.click();
    else location.assign("/missions");
  }

  function syncDeleteButton(actions) {
    const button = actions.querySelector("[data-delete-selected-mission]");
    if (!button) return;
    const runId = selectedRun();
    const label = selectedStateLabel();
    button.disabled = !runId || (label && !terminalLabels.has(label));
    button.title = button.disabled && runId
      ? "运行中或候审批任务不能删除"
      : "删除当前选中的已结束任务；Audit 审计日志会保留";
  }

  function install() {
    if (location.pathname !== "/missions") return;
    const root = document.getElementById("module-page-root");
    const tools = root?.querySelector(".mission-history-tools");
    if (!tools || tools.querySelector(".mission-history-actions")) return;

    const actions = document.createElement("div");
    actions.className = "mission-history-actions";
    actions.innerHTML = `
      <button type="button" class="ghost mission-history-delete" data-delete-selected-mission>删除选中</button>
      <button type="button" class="ghost mission-history-cleanup" data-cleanup-terminal-missions>清理已结束</button>`;
    tools.appendChild(actions);
    syncDeleteButton(actions);

    actions.querySelector("[data-delete-selected-mission]")?.addEventListener("click", async () => {
      const runId = selectedRun();
      if (!runId) return;
      if (!confirm(`删除历史任务 ${runId.slice(0, 8)}？\n\n该任务的 Chronicle / Evidence / Intelligence / Reasoning 持久记录会删除；Audit 审计日志保留。`)) return;
      try {
        const payload = await post(`/api/missions/${encodeURIComponent(runId)}/delete`);
        toast(`已删除任务 ${String(payload.deleted || runId).slice(0, 8)}，剩余 ${payload.remaining ?? "?"} 条。`);
        refreshMissions(true);
      } catch (error) {
        toast(error.message || String(error), true);
      }
    });

    actions.querySelector("[data-cleanup-terminal-missions]")?.addEventListener("click", async () => {
      if (!confirm("清理所有已结束任务？\n\n只会删除完成 / 失败 / 拒绝的 Chronicle 任务记录；运行中和候审批任务会保留，Audit 审计日志也会保留。")) return;
      try {
        const payload = await post("/api/missions/cleanup");
        toast(`已清理 ${payload.count ?? 0} 条历史任务，剩余 ${payload.remaining ?? "?"} 条。`);
        refreshMissions(true);
      } catch (error) {
        toast(error.message || String(error), true);
      }
    });
  }

  const root = document.getElementById("module-page-root");
  if (root) {
    const observer = new MutationObserver(() => queueMicrotask(install));
    observer.observe(root, {childList: true, subtree: true});
  }
  document.addEventListener("click", event => {
    if (!event.target.closest?.("[data-select-run]")) return;
    setTimeout(() => {
      const actions = document.querySelector(".mission-history-actions");
      if (actions) syncDeleteButton(actions);
    }, 0);
  });
  window.addEventListener("popstate", () => setTimeout(install, 0));
  install();
})();
