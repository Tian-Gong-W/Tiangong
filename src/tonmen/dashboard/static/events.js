(() => {
  "use strict";

  let cursor = Number(sessionStorage.getItem("tonmen.event.cursor") || "0") || 0;
  let refreshTimer = null;
  let stopped = false;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));

  function selectedRun() {
    return new URLSearchParams(location.search).get("run");
  }

  function ensureStream() {
    if (location.pathname !== "/missions") return null;
    const root = document.getElementById("module-page-root");
    if (!root) return null;
    let panel = document.getElementById("live-event-stream");
    if (panel) return panel;
    panel = document.createElement("section");
    panel.id = "live-event-stream";
    panel.className = "module-card live-event-card";
    panel.innerHTML = `
      <div class="module-card-head">
        <h2>实时执行流 / Live Event Stream</h2>
        <small>cursor 增量 · stdout / stderr · lifecycle</small>
      </div>
      <pre id="live-event-output" class="terminal live-event-output">等待执行事件…\n</pre>`;
    const head = root.querySelector(".module-page-head");
    if (head?.nextSibling) root.insertBefore(panel, head.nextSibling);
    else root.appendChild(panel);
    return panel;
  }

  function eventLine(event) {
    const data = event.data || {};
    const time = new Date(event.timestamp).toLocaleTimeString();
    if (event.type === "tool.output") {
      const stream = data.stream || "stdout";
      const tool = data.tool || "tool";
      const mission = data.mission_id ? ` ${String(data.mission_id).slice(0, 8)}` : "";
      return `[${time}] [${tool}${mission}] [${stream}] ${String(data.chunk || "").replace(/\n$/, "")}`;
    }
    const mission = data.mission_id ? ` mission=${String(data.mission_id).slice(0, 8)}` : "";
    const step = data.step_id ? ` step=${String(data.step_id).slice(0, 8)}` : "";
    const tool = data.tool ? ` tool=${data.tool}` : "";
    const reason = data.reason ? ` reason=${data.reason}` : "";
    return `[${time}] ${event.type}${mission}${step}${tool}${reason}`;
  }

  function appendEvent(event) {
    window.dispatchEvent(new CustomEvent("tonmen:runtime-event", { detail: event }));
    if (location.pathname !== "/missions") return;
    const wanted = selectedRun();
    const eventMission = event.data?.mission_id;
    if (wanted && eventMission && wanted !== eventMission) return;
    ensureStream();
    const output = document.getElementById("live-event-output");
    if (!output) return;
    if (output.textContent === "等待执行事件…\n") output.textContent = "";
    output.textContent += eventLine(event) + "\n";
    if (output.textContent.length > 180000) output.textContent = output.textContent.slice(-140000);
    output.scrollTop = output.scrollHeight;
  }

  function requestRefresh(event) {
    if (event.type === "tool.output") return;
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => {
      if (document.hidden) return;
      if (location.pathname === "/") {
        document.getElementById("refresh-btn")?.click();
      } else {
        document.querySelector("[data-module-refresh]")?.click();
      }
    }, 120);
  }

  async function poll() {
    while (!stopped) {
      try {
        const response = await fetch(`/api/events?cursor=${cursor}&timeout=20&limit=200`, {
          cache: "no-store",
          headers: { "Accept": "application/json" }
        });
        if (!response.ok) throw new Error(`event stream ${response.status}`);
        const payload = await response.json();
        for (const event of payload.events || []) {
          cursor = Math.max(cursor, Number(event.cursor) || cursor);
          appendEvent(event);
          requestRefresh(event);
        }
        cursor = Math.max(cursor, Number(payload.cursor) || cursor);
        sessionStorage.setItem("tonmen.event.cursor", String(cursor));
      } catch (_) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
  }

  window.addEventListener("beforeunload", () => { stopped = true; });
  ensureStream();
  poll();
})();
