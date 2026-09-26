(() => {
  "use strict";

  const root = document.getElementById("module-page-root");
  if (!root) return;

  const riskNames = {0:"被动",1:"探测",2:"主动",3:"验证",4:"侵入",5:"破坏性"};
  const kindNames = {host:"主机",service:"服务",web:"网站",finding:"漏洞"};
  const severityNames = {info:"信息",low:"低",medium:"中",high:"高",critical:"严重",unknown:"未知"};

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));

  function detailsBlock(title, html) {
    return `<details class="module-simple-details"><summary>${esc(title)}</summary><div>${html}</div></details>`;
  }

  function simplifyTools() {
    if ((location.pathname.replace(/\/+$/, "") || "/") !== "/tools") return;
    root.querySelectorAll(".tool-card:not([data-simple-view])").forEach(card => {
      card.dataset.simpleView = "1";
      const name = card.querySelector("h3")?.textContent?.trim() || "工具";
      const top = card.querySelector(".tool-card-top");
      const statusNode = top?.querySelector(":scope > .module-badge:last-child");
      const available = Boolean(statusNode?.classList.contains("ok"));
      const category = top?.querySelector("h3 + .module-badge")?.textContent?.trim() || "";
      const description = card.querySelector(":scope > p")?.textContent?.trim() || "";
      const meta = [...card.querySelectorAll(".fact-meta .module-badge")];
      const riskText = meta[0]?.textContent?.trim() || "";
      const riskMatch = riskText.match(/L(\d+)/i);
      const risk = riskMatch ? Number(riskMatch[1]) : null;
      const doctor = meta.slice(1).map(node => node.textContent.trim()).filter(Boolean).join(" · ");
      const caps = [...card.querySelectorAll(".caps span")].map(node => node.textContent.trim()).filter(Boolean);
      const advanced = [
        category ? `<div><span>类别</span><code>${esc(category)}</code></div>` : "",
        description ? `<p>${esc(description)}</p>` : "",
        doctor ? `<div><span>检查</span><code>${esc(doctor)}</code></div>` : "",
        caps.length ? `<div class="simple-cap-list">${caps.map(cap => `<code>${esc(cap)}</code>`).join("")}</div>` : "",
      ].join("");
      card.innerHTML = `
        <div class="simple-tool-main">
          <div><h3>${esc(name)}</h3><span>${available ? "可以使用" : "需要处理"}</span></div>
          <span class="module-badge ${available ? "ok" : "bad"}">${available ? "可用" : "不可用"}</span>
        </div>
        <div class="simple-tool-risk"><span>风险</span><strong>${risk === null ? "—" : `L${risk} · ${riskNames[risk] || ""}`}</strong></div>
        ${advanced ? detailsBlock("详细信息", advanced) : ""}`;
    });
  }

  function simplifyIntelligence() {
    if ((location.pathname.replace(/\/+$/, "") || "/") !== "/intelligence") return;
    root.querySelectorAll(".fact-item:not([data-simple-view])").forEach(item => {
      item.dataset.simpleView = "1";
      const h3 = item.querySelector("h3");
      const target = item.querySelector("p")?.textContent?.trim() || "";
      const badges = [...item.querySelectorAll(".fact-meta .module-badge")];
      const kindNode = badges.find(node => node.classList.contains("purple"));
      const kindRaw = kindNode?.textContent?.trim().toLowerCase() || "";
      const severityNode = badges.find(node => !node.classList.contains("purple") && !/^Evidence\s/i.test(node.textContent.trim()));
      const severityRaw = severityNode?.textContent?.trim().toLowerCase() || "";
      const evidenceNode = badges.find(node => /^Evidence\s/i.test(node.textContent.trim()));
      const evidenceId = evidenceNode?.textContent?.replace(/^Evidence\s*/i, "").trim() || "";
      const button = item.querySelector("button[data-open-run]");
      if (kindNode) kindNode.textContent = kindNames[kindRaw] || kindRaw || "信息";
      if (severityNode) severityNode.textContent = severityNames[severityRaw] || severityRaw;
      evidenceNode?.remove();
      if (button) button.textContent = "查看任务";
      const meta = item.querySelector(".fact-meta");
      if (meta && evidenceId) {
        meta.insertAdjacentHTML("afterend", detailsBlock("证据信息", `<div><span>证据 ID</span><code>${esc(evidenceId)}</code></div>${target ? `<div><span>目标</span><code>${esc(target)}</code></div>` : ""}`));
      }
      if (h3 && kindRaw === "finding") item.classList.add("simple-finding");
    });

    const statLabels = root.querySelectorAll(".module-stat span");
    const replacements = ["总数", "服务", "网站", "漏洞"];
    statLabels.forEach((node, index) => { if (replacements[index]) node.textContent = replacements[index]; });
    const head = root.querySelector(".module-card-head h2");
    if (head) head.textContent = "已确认信息";
    const small = root.querySelector(".module-card-head small");
    if (small) small.textContent = "最近任务";
  }

  function fieldMap(dl) {
    const result = {};
    if (!dl) return result;
    const children = [...dl.children];
    for (let i = 0; i < children.length; i += 2) {
      const key = children[i]?.textContent?.trim();
      const value = children[i + 1]?.textContent?.trim();
      if (key) result[key] = value || "—";
    }
    return result;
  }

  function setting(fields, keys, fallback = "—") {
    for (const key of keys) if (fields[key] != null) return fields[key];
    return fallback;
  }

  function simplifySettings() {
    if ((location.pathname.replace(/\/+$/, "") || "/") !== "/settings") return;
    const cards = [...root.querySelectorAll(".module-card")];
    const configCard = cards.find(card => card.querySelector(".settings-grid"));
    if (configCard && configCard.dataset.simpleView !== "1") {
      configCard.dataset.simpleView = "1";
      const dl = configCard.querySelector(".settings-grid");
      const fields = fieldMap(dl);
      const workspace = setting(fields, ["workspace", "workspace_path"]);
      const host = setting(fields, ["bind_host"], "127.0.0.1");
      const port = setting(fields, ["bind_port"], "8888");
      const timeout = setting(fields, ["command_timeout_seconds"], "—");
      const allowed = setting(fields, ["allowed_targets"], "—");
      const original = dl?.outerHTML || "";
      const body = configCard.querySelector(".module-card-body");
      const title = configCard.querySelector(".module-card-head h2");
      if (title) title.textContent = "运行设置";
      configCard.querySelector(".module-card-head small")?.remove();
      if (body) body.innerHTML = `
        <div class="simple-settings-grid">
          <div><span>运行目录</span><strong title="${esc(workspace)}">${esc(workspace)}</strong></div>
          <div><span>控制台</span><strong>${esc(host)}:${esc(port)}</strong></div>
          <div><span>命令超时</span><strong>${esc(timeout)}${timeout !== "—" ? " 秒" : ""}</strong></div>
          <div><span>授权目标</span><strong title="${esc(allowed)}">${esc(allowed)}</strong></div>
        </div>
        ${original ? detailsBlock("全部设置", original) : ""}`;
    }

    const doctorCard = cards.find(card => card !== configCard && card.querySelector(".fact-list"));
    if (doctorCard && doctorCard.dataset.simpleView !== "1") {
      doctorCard.dataset.simpleView = "1";
      const items = [...doctorCard.querySelectorAll(".fact-item")];
      const failed = items.filter(item => item.querySelector(".module-badge.bad"));
      const original = doctorCard.querySelector(".module-card-body")?.innerHTML || "";
      const body = doctorCard.querySelector(".module-card-body");
      const title = doctorCard.querySelector(".module-card-head h2");
      const badge = doctorCard.querySelector(".module-card-head .module-badge");
      if (title) title.textContent = "运行检查";
      if (badge) {
        badge.textContent = failed.length ? "需处理" : "正常";
        badge.classList.toggle("ok", failed.length === 0);
        badge.classList.toggle("warn", failed.length > 0);
      }
      const visibleFailures = failed.map(item => {
        const name = item.querySelector("h3")?.childNodes[0]?.textContent?.trim() || item.querySelector("h3")?.textContent?.trim() || "检查项";
        const detail = item.querySelector("p")?.textContent?.trim() || "需要处理";
        return `<div class="simple-check-fail"><strong>${esc(name)}</strong><span>${esc(detail)}</span></div>`;
      }).join("");
      if (body) body.innerHTML = `${failed.length ? visibleFailures : `<div class="simple-check-ok">✓ 当前运行正常</div>`}${detailsBlock("检查详情", original)}`;
    }
  }

  function apply() {
    simplifyTools();
    simplifyIntelligence();
    simplifySettings();
  }

  const observer = new MutationObserver(apply);
  observer.observe(root, {childList:true, subtree:true});
  window.addEventListener("popstate", () => setTimeout(apply, 0));
  document.addEventListener("click", event => {
    if (event.target.closest?.(".nav-item,[data-route-go]")) setTimeout(apply, 20);
  }, true);
  apply();
})();
