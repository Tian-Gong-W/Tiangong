(() => {
  "use strict";
  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const navNames = {
    "儀表總覽":["总览", ""], "任務":["任务", ""], "天域":["授权范围", "天域"],
    "天律":["安全策略", "天律"], "天工":["工具", "天工"], "天役":["执行节点", "天役"],
    "天鑑":["情报", "天鑑"], "天策":["AI 推理", "天策"], "主導":["AI 配置", "主導"],
    "天衡":["任务流程", "天衡"], "天冊":["任务记录", "天冊"], "審批":["人工确认", ""],
    "設定":["设置", ""]
  };
  const states = {
    waiting_approval:"等待批准", succeeded:"已完成", skipped:"已跳过", denied:"已拒绝",
    failed:"失败", running:"执行中", pending:"等待执行", degraded:"部分完成"
  };
  const pageCopy = {
    "/missions":["任务", "查看任务、步骤和结果。"],
    "/scope":["授权范围", "管理允许执行的目标。"],
    "/guard":["安全策略", "查看风险规则和审批状态。"],
    "/tools":["工具", "查看工具是否可用。"],
    "/intelligence":["情报", "查看从证据中确认的信息。"],
    "/reasoner":["AI 推理", "查看系统为什么这样判断。"],
    "/lead":["AI 配置", "连接模型并查看 AI 主控。"],
    "/loop":["任务流程", "查看任务执行进度。"],
    "/chronicle":["任务记录", "查看历史任务和审计。"],
    "/approval":["人工确认", "处理需要你确认的主动验证。"],
    "/settings":["设置", "查看当前运行设置。"]
  };
  const exactText = {
    "Total":"总数", "Running":"执行中", "Waiting approval":"等待批准", "Failed / denied":"失败 / 拒绝",
    "Execution Content":"执行结果", "任务历史":"任务记录", "Allowed Scope":"已授权", "Denied Scope":"已拒绝",
    "Built-in loopback authority":"本机默认允许", "Project-authorized target":"项目已授权", "Explicit deny rule":"明确拒绝",
    "Mode":"模式", "Allowed rules":"允许规则", "Denied rules":"拒绝规则", "Pending approvals":"等待确认",
    "Evidence-backed Facts":"已确认信息", "Mission Chronicle":"任务记录", "Project Configuration":"项目设置",
    "Doctor / Runtime Readiness":"运行检查", "Lead Runtime":"AI 主控", "Council Progress":"AI 评审进度",
    "Authority Boundary":"权限边界", "Current Directive":"当前判断", "Telemetry":"调用统计",
    "FINAL / INTERIM ARTIFACT":"", "完整执行报告 / Mission Report":"任务报告",
    "Finding Aggregation":"漏洞合并", "Finding Verification":"漏洞确认", "Resolved Asset Coverage / 解析资产覆盖":"资产覆盖",
    "时间 / Time Semantics":"时间", "治理 / Governance":"安全控制", "执行步骤 / Steps":"执行步骤",
    "原始 Finding Facts":"原始发现", "Executed Requests / Payloads":"执行请求", "Assessment Council · 7–10 rounds":"AI 评审",
    "Reasoning":"判断记录", "Raw Evidence":"原始证据", "Target":"目标", "State":"状态",
    "Started · Local / UTC":"开始时间", "Finished · Local / UTC":"结束时间", "Resolved assets":"解析地址",
    "Needs Scope":"需授权", "Unique findings":"漏洞数", "Finding instances":"命中次数", "Duplicates collapsed":"已合并重复",
    "Affected backends":"受影响地址", "Evidence confirmed":"证据确认", "Attribution contradicted":"归因冲突",
    "Rounds":"评审轮次", "Subagent reviews":"子代理评审", "Address":"地址", "Family":"类型", "Scope":"授权",
    "Direct Nmap":"直接扫描", "Scanned":"已扫描", "Coverage":"覆盖", "Tool":"工具", "Risk":"风险",
    "Approval":"需确认", "Exit":"退出码", "Backend":"地址", "Instances":"次数", "Server":"服务",
    "Evidence":"证据", "Attribution":"归因", "Evidence IDs":"证据 ID", "Template":"模板",
    "Observed Server":"检测服务", "Nmap scanned":"Nmap 已扫", "Other resolved/not scanned":"其他未扫地址",
    "Executed request / payload":"执行请求", "Response":"响应", "Aggregate ID":"合并 ID",
    "Instances collapsed":"合并重复数", "Template Matched":"模板命中", "Evidence Confirmed":"证据确认"
  };
  const phraseText = [
    ["Template: matched", "模板：已命中"], ["Template: unknown", "模板：未知"],
    ["Evidence: confirmed", "证据：已确认"], ["Evidence: observed", "证据：已观察"], ["Evidence: unknown", "证据：未知"],
    ["Attribution: supported", "归因：支持"], ["Attribution: contradicted", "归因：冲突"], ["Attribution: unverified", "归因：未确认"],
    ["Backend: same_backend", "地址：一致"], ["Backend: different_backend", "地址：不同"], ["Backend: different_resolved_backend", "地址：不同解析节点"],
    ["Scope: authorized", "授权：已允许"], ["Scope: needs_scope", "授权：需确认"],
    ["Coverage: scanned", "覆盖：已扫描"], ["Coverage: authorized_uncovered", "覆盖：已授权未扫描"],
    ["confidence ", "可信度 "], ["variance yes", "节点差异 有"], ["variance no", "节点差异 无"]
  ];

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

  function setText(selector, text) {
    const node = document.querySelector(selector);
    if (node && node.textContent !== text) node.textContent = text;
  }

  function simplifyHeader() {
    setText(".brand-tagline", "安全自动化");
    setText(".header-slogan span", "自动执行，关键步骤由你确认");
    document.querySelector(".header-slogan small")?.remove();
  }

  function simplifyNav() {
    document.querySelectorAll(".nav-item b").forEach(node => {
      if (node.dataset.simpleNav === "1") return;
      const original = node.childNodes[0]?.textContent?.trim() || node.textContent.trim();
      const mapped = navNames[original];
      if (!mapped) return;
      node.dataset.simpleNav = "1";
      node.replaceChildren(document.createTextNode(mapped[0]));
      if (mapped[1]) {
        const small = document.createElement("small");
        small.className = "plain-nav-name";
        small.textContent = mapped[1];
        node.appendChild(small);
      }
    });
  }

  function simplifyOverview() {
    setText(".deck-title strong", "操作");
    document.querySelector(".deck-title small")?.remove();
    setText("#mission-panel .panel-title h2", "当前任务");
    setText("#scope-panel .panel-title h2", "授权范围");
    setText("#intel-panel .panel-title h2", "已确认信息");
    setText("#reason-panel .panel-title h2", "下一步建议");
    setText("#approval-panel .panel-title h2", "需要确认");
    setText("#chronicle-panel .panel-title h2", "任务记录");
    setText(".graph-panel .panel-title h2", "证据关系");
    setText(".loop-visual .subhead", "任务流程");
    setText("#scope-panel .notice", "仅限已授权目标");
    setText(".reason-label:not(.secondary)", "建议操作");
    document.querySelector(".reason-label.secondary")?.classList.add("simple-hide");
    document.querySelector(".decision-legend")?.classList.add("simple-hide");
    setText(".approval-foot", "主动验证需要你确认");

    const metaLabels = document.querySelectorAll(".mission-meta span");
    if (metaLabels[0]) metaLabels[0].textContent = "目标";
    if (metaLabels[1]) metaLabels[1].textContent = "状态";

    setText("#new-mission-btn", "＋ 新任务");
    setText("#empty-new-mission-btn", "新任务");
    setText("#deck-new-mission", "▶ 新任务");
    setText("#deck-refresh", "↻ 刷新");
    setText("#deck-resume", "∞ 继续任务");
    setText("#deck-evidence", "◉ 查看证据");
    setText("#deck-retry", "↻ 重新执行");

    const missionDialog = document.getElementById("mission-dialog");
    missionDialog?.querySelector(".kicker")?.remove();
    const missionTitle = missionDialog?.querySelector("h2"); if (missionTitle) missionTitle.textContent = "新任务";
    const targetLabel = missionDialog?.querySelector("label");
    if (targetLabel && !targetLabel.dataset.simpleLabel) {
      targetLabel.dataset.simpleLabel = "1";
      const input = targetLabel.querySelector("input");
      targetLabel.childNodes[0].textContent = "目标";
      if (input) input.placeholder = "输入已授权的域名、IP 或 URL";
    }
    const startButton = missionDialog?.querySelector('button[type="submit"]');
    if (startButton) startButton.textContent = "开始任务";
    const missionNote = missionDialog?.querySelector(".dialog-note");
    if (missionNote) missionNote.textContent = "只执行已授权范围内的计划；主动验证会先询问你。";

    const evidenceDialog = document.getElementById("evidence-dialog");
    evidenceDialog?.querySelector(".kicker")?.remove();
    const evidenceTitle = evidenceDialog?.querySelector("h2"); if (evidenceTitle) evidenceTitle.textContent = "证据";
  }

  function simplifyModulePage() {
    const copy = pageCopy[location.pathname.replace(/\/+$/, "") || "/"];
    if (!copy) return;
    const head = document.querySelector(".module-page-head");
    if (!head) return;
    head.querySelector(".kicker")?.remove();
    const h1 = head.querySelector("h1");
    if (h1 && h1.dataset.simpleTitle !== "1") {
      h1.dataset.simpleTitle = "1";
      h1.textContent = copy[0];
    }
    const p = head.querySelector("p"); if (p) p.textContent = copy[1];
    const live = head.querySelector(".module-live");
    if (live) live.innerHTML = "<i></i><span>自动更新</span>";
  }

  function translateNode(node) {
    if (!node || node.closest("pre,.terminal,.cmd,.stdout,.stderr")) return;
    const text = node.textContent?.trim();
    if (!text) return;
    if (Object.prototype.hasOwnProperty.call(exactText, text)) {
      const replacement = exactText[text];
      if (!replacement) node.classList.add("simple-hide");
      else node.textContent = replacement;
      return;
    }
    let replacement = text;
    for (const [from, to] of phraseText) replacement = replacement.replaceAll(from, to);
    if (replacement !== text) node.textContent = replacement;
  }

  function simplifyGeneratedCopy() {
    const selectors = [
      ".module-page-root h2", ".module-page-root h3", ".module-page-root th", ".module-page-root .module-stat span",
      ".module-page-root .module-card-head small", ".module-page-root .module-badge", ".module-page-root .scope-detailed-row small",
      ".mission-report-dialog h2", ".mission-report-dialog h3", ".mission-report-dialog h4", ".mission-report-dialog th",
      ".mission-report-dialog .report-summary span", ".mission-report-dialog .report-kv span", ".mission-report-dialog .module-badge"
    ];
    document.querySelectorAll(selectors.join(",")).forEach(translateNode);

    const report = document.getElementById("mission-report-dialog");
    if (report) {
      const headTag = report.querySelector(".report-head > div > span");
      if (headTag) headTag.classList.add("simple-hide");
      const title = report.querySelector(".report-head h2"); if (title) title.textContent = "任务报告";
      report.querySelectorAll(".report-section p").forEach(p => {
        const text = p.textContent || "";
        if (text.includes("Template Matched") || text.includes("CVE/root-cause Attribution")) {
          p.textContent = "模板命中、证据确认、漏洞归因分别判断。";
        } else if (text.includes("DNS resolution is observation only")) {
          p.textContent = "DNS 解析只用于观察，不会自动扩大授权范围。";
        } else if (text.includes("canonical timestamps use UTC")) {
          p.textContent = "报告时间统一记录为 UTC；界面同时显示本地时间。";
        }
      });
      report.querySelectorAll("td").forEach(td => {
        if (td.children.length) return;
        const value = td.textContent.trim();
        if (value === "yes") td.textContent = "是";
        if (value === "no") td.textContent = "否";
      });
    }
  }

  function simplifyStates() {
    document.querySelectorAll(".step-state,.state-pill,.module-badge").forEach(node => {
      const state = [...node.classList].find(name => states[name]);
      if (state && node.textContent !== states[state]) node.textContent = states[state];
    });
  }

  function simplifyApprovalButtons() {
    document.querySelectorAll("#approve-btn,.deck-approve,[data-approve-run]").forEach(button => {
      if (!button.dataset.easyLabel) button.dataset.easyLabel = "1";
      if (!button.disabled && !button.classList.contains("easy-confirm") && !/执行中|受理/.test(button.textContent)) {
        button.textContent = "批准并继续";
      }
    });
  }

  function simplifyLanguage() {
    simplifyHeader();
    simplifyNav();
    simplifyOverview();
    simplifyModulePage();
    simplifyGeneratedCopy();
    simplifyStates();
    simplifyApprovalButtons();
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
      button.textContent = "再次点击确认";
      button.classList.add("easy-confirm");
      toast("这一步会对已授权目标做主动验证。再次点击即可继续。");
      setTimeout(() => {
        if (Date.now() > Number(button.dataset.confirmUntil || 0)) {
          button.textContent = "批准并继续";
          button.classList.remove("easy-confirm");
        }
      }, 8200);
      return;
    }
    button.disabled = true;
    button.textContent = "执行中…";
    try {
      const result = await api(`/api/missions/${encodeURIComponent(runId)}/approve`, {method:"POST"});
      toast(result.message || "已开始，后台执行中。页面可继续使用。");
      pollApproval(runId);
    } catch (error) {
      button.disabled = false;
      button.textContent = "批准并继续";
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
