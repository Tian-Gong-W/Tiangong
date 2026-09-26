(() => {
  "use strict";

  const root = document.getElementById("module-page-root");
  if (!root) return;

  const route = () => location.pathname.replace(/\/+$/, "") || "/";
  const actionNames = {
    continue: "继续任务",
    request_approval: "等待确认",
    skip: "跳过",
    review: "人工复核",
    stop: "停止",
    complete: "完成",
    continue_governed_plan: "继续任务",
    await_human_approval: "等待确认",
    review_failure_evidence: "检查失败证据",
    finalize_report: "生成报告",
    stop_for_human_review: "等待人工复核",
  };
  const loopNames = {session:"开始",iteration:"执行记录",stop:"结束"};
  const auditNames = {allow:"允许",deny:"拒绝",error:"错误",timeout:"超时",approval:"需确认"};

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));

  function details(title, html) {
    return `<details class="final-simple-details"><summary>${esc(title)}</summary><div>${html}</div></details>`;
  }

  function hideCardSmall(card) {
    card?.querySelector(".module-card-head small")?.classList.add("final-simple-hide");
  }

  function simplifyOverview() {
    if (route() !== "/") return;
    const graphNames = {Mission:"任务",Observation:"观察",Evidence:"证据",Intelligence:"情报",Reasoning:"判断"};
    document.querySelectorAll(".nodes text").forEach(node => {
      const value = node.textContent?.trim();
      if (graphNames[value]) node.textContent = graphNames[value];
    });
    const missionDialog = document.getElementById("mission-dialog");
    missionDialog?.querySelector(".kicker")?.classList.add("final-simple-hide");
    const missionTitle = missionDialog?.querySelector("h2");
    if (missionTitle) missionTitle.textContent = "新任务";
    const evidenceDialog = document.getElementById("evidence-dialog");
    evidenceDialog?.querySelector(".kicker")?.classList.add("final-simple-hide");
    const evidenceTitle = evidenceDialog?.querySelector("h2");
    if (evidenceTitle) evidenceTitle.textContent = "证据";
  }

  function simplifyMissions() {
    if (route() !== "/missions") return;
    const cards = [...root.querySelectorAll(".module-card")];
    cards.forEach(card => {
      const h2 = card.querySelector(".module-card-head h2");
      const text = h2?.textContent?.trim() || "";
      if (/任务历史/.test(text)) h2.textContent = "任务记录";
      if (/任务详情/.test(text)) h2.textContent = "任务详情";
      if (/执行内容|Execution Content/.test(text)) h2.textContent = "执行结果";
      hideCardSmall(card);
    });
    const headers = {Run:"任务",Target:"目标",State:"状态",Started:"开始时间"};
    root.querySelectorAll("th").forEach(th => { const t = th.textContent.trim(); if (headers[t]) th.textContent = headers[t]; });
    root.querySelectorAll(".detail-title small").forEach(node => {
      if (/Run\s/i.test(node.textContent || "")) node.classList.add("final-simple-hide");
    });
  }

  function simplifyScope() {
    if (route() !== "/scope") return;
    root.querySelectorAll(".module-card").forEach(card => {
      const h2 = card.querySelector("h2");
      const text = h2?.textContent?.trim() || "";
      if (text === "Allowed Scope" || text === "已授权") h2.textContent = "已授权";
      if (text === "Denied Scope" || text === "已拒绝") h2.textContent = "明确拒绝";
      hideCardSmall(card);
    });
  }

  function simplifyGuard() {
    if (route() !== "/guard") return;
    const cards = [...root.querySelectorAll(".module-card")];
    cards.forEach(card => {
      const h2 = card.querySelector("h2");
      const text = h2?.textContent?.trim() || "";
      if (/Policy Rules/.test(text)) h2.textContent = "规则";
      if (/Audit|审计/.test(text)) h2.textContent = "操作记录";
      hideCardSmall(card);
    });
    const policyCard = cards.find(card => card.querySelector(".policy-rule"));
    const ladder = policyCard?.querySelector(".risk-ladder");
    if (ladder && !ladder.closest("details")) {
      const box = document.createElement("details");
      box.className = "final-simple-details";
      box.innerHTML = "<summary>风险等级</summary>";
      ladder.parentNode.insertBefore(box, ladder);
      box.appendChild(ladder);
    }
  }

  function simplifyReasoner() {
    if (route() !== "/reasoner") return;
    const card = root.querySelector(".module-card");
    const title = card?.querySelector(".module-card-head h2");
    if (title) title.textContent = "判断记录";
    hideCardSmall(card);
    root.querySelectorAll(".decision-item:not([data-final-simple])").forEach(item => {
      item.dataset.finalSimple = "1";
      const h3 = item.querySelector("h3");
      const original = h3?.textContent?.trim() || "";
      const parts = original.split("·");
      const rawAction = (parts.shift() || "").trim().toLowerCase();
      const target = parts.join("·").trim();
      const action = actionNames[rawAction] || rawAction || "判断";
      if (h3) h3.textContent = target ? `${action} · ${target}` : action;

      const meta = item.querySelector(".decision-meta");
      if (!meta) return;
      const badges = [...meta.querySelectorAll(".module-badge")];
      const human = badges.find(node => /需人决|可自治|需要你确认|自动继续/.test(node.textContent || ""));
      if (human) human.textContent = /需人决|需要你确认/.test(human.textContent || "") ? "需要你确认" : "自动继续";
      const technical = badges.filter(node => node !== human).map(node => `<code>${esc(node.textContent.trim())}</code>`).join("");
      badges.filter(node => node !== human).forEach(node => node.remove());
      const button = meta.querySelector("button[data-open-run]");
      if (button) button.textContent = "查看任务";
      if (technical) meta.insertAdjacentHTML("afterend", details("依据", `<div class="final-inline-codes">${technical}</div>`));
    });
  }

  function simplifyLoop() {
    if (route() !== "/loop") return;
    root.querySelectorAll(".module-card").forEach(card => {
      const h2 = card.querySelector("h2");
      const text = h2?.textContent?.trim() || "";
      if (/当前循环/.test(text)) h2.textContent = "当前流程";
      if (/Loop Provenance/.test(text)) h2.textContent = "流程记录";
      hideCardSmall(card);
    });
    root.querySelectorAll(".loop-item:not([data-final-simple])").forEach(item => {
      item.dataset.finalSimple = "1";
      const h3 = item.querySelector("h3");
      const original = h3?.textContent?.trim() || "";
      const parts = original.split("·");
      const type = (parts.shift() || "").trim().toLowerCase();
      const target = parts.join("·").trim();
      if (h3) h3.textContent = `${loopNames[type] || "记录"}${target ? ` · ${target}` : ""}`;
      const meta = item.querySelector(".loop-meta");
      if (!meta) return;
      const badges = [...meta.querySelectorAll(".module-badge")];
      const technical = badges.map(node => `<code>${esc(node.textContent.trim())}</code>`).join("");
      badges.forEach(node => node.remove());
      const button = meta.querySelector("button[data-open-run]");
      if (button) button.textContent = "查看任务";
      if (technical) meta.insertAdjacentHTML("afterend", details("详细信息", `<div class="final-inline-codes">${technical}</div>`));
    });
  }

  function simplifyChronicle() {
    if (route() !== "/chronicle") return;
    const cards = [...root.querySelectorAll(".module-card")];
    cards.forEach(card => {
      const h2 = card.querySelector("h2");
      const text = h2?.textContent?.trim() || "";
      if (/Mission Chronicle|任务记录/.test(text)) h2.textContent = "任务记录";
      if (/Audit|审计/.test(text)) h2.textContent = "操作记录";
      hideCardSmall(card);
    });
    const headers = {Time:"时间",Target:"目标",Run:"任务",State:"状态"};
    root.querySelectorAll("th").forEach(th => { const t = th.textContent.trim(); if (headers[t]) th.textContent = headers[t]; });
    root.querySelectorAll(".audit-item .decision").forEach(node => {
      const value = node.textContent.trim().toLowerCase();
      if (auditNames[value]) node.textContent = auditNames[value];
    });
  }

  function simplifyApproval() {
    if (route() !== "/approval") return;
    const stats = [...root.querySelectorAll(".module-stat")];
    if (stats[0]?.querySelector("span")) stats[0].querySelector("span").textContent = "待确认";
    if (stats[1]?.querySelector("span")) stats[1].querySelector("span").textContent = "最近任务";
    stats.slice(2).forEach(node => node.classList.add("final-simple-hide"));
    const card = root.querySelector(".module-card");
    const h2 = card?.querySelector("h2");
    if (h2) h2.textContent = "待确认";
    hideCardSmall(card);

    root.querySelectorAll(".approval-workitem:not([data-final-simple])").forEach(item => {
      item.dataset.finalSimple = "1";
      item.querySelectorAll(".fact-meta .module-badge").forEach(node => {
        node.textContent = node.textContent.replace(/^Run\s+/i, "任务 ").replace(/^Risk\s+/i, "风险 ").replace(/^Evidence\s+/i, "证据 ");
      });
      const pre = item.querySelector("pre.terminal");
      if (pre && !pre.closest("details")) {
        const box = document.createElement("details");
        box.className = "final-simple-details final-evidence-preview";
        box.innerHTML = "<summary>证据预览</summary>";
        pre.parentNode.insertBefore(box, pre);
        box.appendChild(pre);
      }
      const approve = item.querySelector("button[data-approve-run]");
      if (approve) approve.textContent = "批准并继续";
      const open = item.querySelector("button[data-open-run]");
      if (open) open.textContent = "查看任务";
    });
  }

  function simplifyGeneric() {
    root.querySelectorAll(".module-card-head small").forEach(node => {
      const text = node.textContent || "";
      if (/Fact\s*→|session\s*·|rounds|subagents|argv|stdout|stderr|persisted runs|EVENT|Scope\s*→/i.test(text)) node.classList.add("final-simple-hide");
    });
    root.querySelectorAll(".module-toolbar button").forEach(button => {
      button.textContent = button.textContent.replace("▶ 执行新任务", "新任务").replace("↻ 刷新实时数据", "刷新").replace("打开审批中心", "人工确认");
    });
  }

  function apply() {
    simplifyOverview();
    simplifyMissions();
    simplifyScope();
    simplifyGuard();
    simplifyReasoner();
    simplifyLoop();
    simplifyChronicle();
    simplifyApproval();
    simplifyGeneric();
  }

  const observer = new MutationObserver(apply);
  observer.observe(document.documentElement, {childList:true, subtree:true});
  window.addEventListener("popstate", () => setTimeout(apply, 0));
  document.addEventListener("click", event => {
    if (event.target.closest?.(".nav-item,[data-route-go]")) setTimeout(apply, 30);
  }, true);
  apply();
})();
