(() => {
  "use strict";

  const path = location.pathname.replace(/\/+$/, "") || "/";

  function installArtifactNav() {
    const nav = document.querySelector(".operator-nav");
    if (!nav || nav.querySelector('a[href="/artifacts"]')) return;
    const link = document.createElement("a");
    link.href = "/artifacts";
    link.className = path === "/artifacts" ? "active" : "";
    link.innerHTML = `<span class="op-icon">◇</span><span><strong>逆向 / Binary</strong><small>Artifact 静态分析 · 不执行</small></span>`;
    const plan = nav.querySelector("[data-operator-plan]");
    nav.insertBefore(link, plan || null);
  }

  installArtifactNav();
  if (path !== "/artifacts") return;

  const MAX_BYTES = 32 * 1024 * 1024;
  const csrf = document.querySelector('meta[name="tonmen-csrf"]')?.content || "";
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const short = value => String(value || "").slice(0, 12);
  const sizeText = value => {
    const bytes = Number(value || 0);
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
  };

  async function api(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data;
  }

  function mount() {
    document.getElementById("overview")?.classList.add("hidden");
    const stage = document.querySelector(".main-stage");
    if (!stage || document.getElementById("artifact-workbench")) return;
    const root = document.createElement("section");
    root.id = "artifact-workbench";
    root.className = "artifact-workbench";
    root.innerHTML = `
      <div class="artifact-titlebar">
        <div><span class="artifact-kicker">逆向 / Binary Intelligence</span><h1>Artifact 静态分析</h1><p>上传到 TONMEN 工作区后只做内容寻址与静态格式分析。不会加载、启动或执行文件。</p></div>
        <div class="artifact-safety"><strong>STATIC ONLY</strong><span>EXECUTION OFF</span><small>Max 32 MiB · SHA-256 addressed</small></div>
      </div>
      <section class="artifact-upload-card">
        <div><strong>上传 Artifact</strong><p>ELF / PE / Mach-O / unknown。浏览器只发送文件 bytes，不发送服务器路径。</p></div>
        <label class="artifact-file-label"><input type="file" id="artifact-file"><span id="artifact-file-name">选择本地文件</span></label>
        <button class="primary" id="artifact-inspect" type="button" disabled>静态检查</button>
        <div id="artifact-upload-state" class="artifact-upload-state">等待文件</div>
      </section>
      <div class="artifact-layout">
        <section class="artifact-panel">
          <div class="artifact-panel-head"><div><h2>Artifact Records</h2><small>内容寻址记录</small></div><button class="ghost" id="artifact-refresh" type="button">↻ 刷新</button></div>
          <div id="artifact-list" class="artifact-list"><div class="artifact-empty">正在读取…</div></div>
        </section>
        <section class="artifact-panel artifact-detail-panel">
          <div class="artifact-panel-head"><div><h2>Static Report</h2><small>格式 / 架构 / Mitigations</small></div><span id="artifact-integrity" class="artifact-integrity">未选择</span></div>
          <div id="artifact-detail" class="artifact-detail"><div class="artifact-empty">选择左侧 Artifact 查看报告。</div></div>
        </section>
      </div>
      <section class="artifact-boundary">
        <strong>执行边界</strong>
        <span>本工作台不执行样本、不运行 shellcode、不生成/投递 ROP、不做持久化。后续反汇编/CFG 也只进入 Evidence/Report。</span>
      </section>`;
    stage.appendChild(root);
  }

  function selectedId() {
    return document.querySelector("#artifact-list .artifact-row.active")?.dataset.artifactId || "";
  }

  function renderList(entries, activeId = "") {
    const list = document.getElementById("artifact-list");
    if (!list) return;
    if (!entries.length) {
      list.innerHTML = `<div class="artifact-empty">还没有 Artifact。选择本地文件开始静态检查。</div>`;
      return;
    }
    list.innerHTML = entries.map(item => `
      <button class="artifact-row ${item.artifact_id === activeId ? "active" : ""}" type="button" data-artifact-id="${esc(item.artifact_id)}">
        <span class="artifact-format">${esc(String(item.format || "unknown").toUpperCase())}</span>
        <span class="artifact-row-main"><strong>${esc(item.source_name || "artifact")}</strong><small>${esc(short(item.artifact_id))} · ${esc(item.architecture || "unknown")}${item.bitness ? ` · ${esc(item.bitness)}-bit` : ""}</small></span>
        <span class="artifact-size">${esc(sizeText(item.size))}</span>
      </button>`).join("");
    list.querySelectorAll("[data-artifact-id]").forEach(button => button.addEventListener("click", () => loadArtifact(button.dataset.artifactId)));
  }

  function mitigationRows(mitigations) {
    const entries = Object.entries(mitigations || {});
    if (!entries.length) return `<div class="artifact-empty compact">当前格式没有可解析的基础 mitigation 标记。</div>`;
    return `<div class="artifact-mitigations">${entries.map(([name, value]) => {
      const state = value === true ? "on" : value === false ? "off" : "unknown";
      const text = value === true ? "Observed" : value === false ? "Not observed" : "Unknown";
      return `<div><span>${esc(name)}</span><b class="${state}">${esc(text)}</b></div>`;
    }).join("")}</div>`;
  }

  function renderDetail(report) {
    const detail = document.getElementById("artifact-detail");
    const integrity = document.getElementById("artifact-integrity");
    if (!detail || !integrity) return;
    integrity.textContent = "SHA-256 VERIFIED";
    integrity.className = "artifact-integrity ok";
    const metadata = Object.entries(report.metadata || {}).map(([key, value]) => `<div><span>${esc(key)}</span><code>${esc(value)}</code></div>`).join("");
    const warnings = (report.warnings || []).map(item => `<li>${esc(item)}</li>`).join("");
    detail.innerHTML = `
      <div class="artifact-identity">
        <div><span>Source name</span><strong>${esc(report.source_name)}</strong></div>
        <div><span>Format</span><strong>${esc(String(report.format || "unknown").toUpperCase())}</strong></div>
        <div><span>Architecture</span><strong>${esc(report.architecture || "unknown")}</strong></div>
        <div><span>Bitness / Endian</span><strong>${report.bitness ? `${esc(report.bitness)}-bit` : "—"} · ${esc(report.endianness || "—")}</strong></div>
        <div><span>Size</span><strong>${esc(sizeText(report.size))}</strong></div>
        <div><span>Execution</span><strong class="artifact-off">OFF</strong></div>
      </div>
      <div class="artifact-hash"><span>SHA-256</span><code>${esc(report.sha256)}</code></div>
      <h3>Mitigation observations</h3>
      ${mitigationRows(report.mitigations)}
      <h3>Parsed metadata</h3>
      <div class="artifact-metadata">${metadata || `<div><span>metadata</span><code>none</code></div>`}</div>
      ${warnings ? `<h3>Parser warnings</h3><ul class="artifact-warnings">${warnings}</ul>` : ""}
      <div class="artifact-detail-actions"><span>Content-addressed · execution_performed=false</span><button class="danger" type="button" id="artifact-delete">删除 Artifact</button></div>`;
    document.getElementById("artifact-delete")?.addEventListener("click", () => deleteArtifact(report.artifact_id));
  }

  async function refreshList(preferred = "") {
    const payload = await api("/api/artifacts");
    const entries = payload.artifacts || [];
    const active = preferred || selectedId();
    renderList(entries, active);
    if (active && entries.some(item => item.artifact_id === active)) {
      document.querySelector(`[data-artifact-id="${CSS.escape(active)}"]`)?.classList.add("active");
    }
    return entries;
  }

  async function loadArtifact(id) {
    if (!id) return;
    try {
      const report = await api(`/api/artifacts/${encodeURIComponent(id)}`);
      document.querySelectorAll("#artifact-list .artifact-row").forEach(row => row.classList.toggle("active", row.dataset.artifactId === id));
      renderDetail(report);
    } catch (error) {
      const detail = document.getElementById("artifact-detail");
      const integrity = document.getElementById("artifact-integrity");
      if (integrity) { integrity.textContent = "INTEGRITY ERROR"; integrity.className = "artifact-integrity bad"; }
      if (detail) detail.innerHTML = `<div class="artifact-empty error">读取失败：${esc(error.message || error)}</div>`;
    }
  }

  async function uploadArtifact() {
    const input = document.getElementById("artifact-file");
    const button = document.getElementById("artifact-inspect");
    const state = document.getElementById("artifact-upload-state");
    const file = input?.files?.[0];
    if (!file || !button || !state) return;
    if (file.size > MAX_BYTES) {
      state.textContent = "拒绝：文件超过 32 MiB";
      state.className = "artifact-upload-state error";
      return;
    }
    button.disabled = true;
    state.textContent = "静态检查中…";
    state.className = "artifact-upload-state busy";
    try {
      const report = await api("/api/artifacts/inspect", {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-TONMEN-CSRF": csrf,
          "X-TONMEN-FILENAME": encodeURIComponent(file.name || "artifact"),
        },
        body: file,
      });
      state.textContent = `完成 · ${short(report.artifact_id)} · 未执行`;
      state.className = "artifact-upload-state ok";
      await refreshList(report.artifact_id);
      await loadArtifact(report.artifact_id);
    } catch (error) {
      state.textContent = `失败：${error.message || error}`;
      state.className = "artifact-upload-state error";
    } finally {
      button.disabled = false;
    }
  }

  async function deleteArtifact(id) {
    if (!id || !confirm("删除此 Artifact 的 blob 与静态报告？此操作不会影响 Mission 记录。")) return;
    try {
      await api(`/api/artifacts/${encodeURIComponent(id)}/delete`, {
        method: "POST",
        headers: {"Content-Type":"application/json", "X-TONMEN-CSRF": csrf},
        body: "{}",
      });
      const detail = document.getElementById("artifact-detail");
      const integrity = document.getElementById("artifact-integrity");
      if (integrity) { integrity.textContent = "已删除"; integrity.className = "artifact-integrity"; }
      if (detail) detail.innerHTML = `<div class="artifact-empty">Artifact 已删除。</div>`;
      await refreshList();
    } catch (error) {
      alert(`删除失败：${error.message || error}`);
    }
  }

  mount();
  const input = document.getElementById("artifact-file");
  const inspect = document.getElementById("artifact-inspect");
  input?.addEventListener("change", () => {
    const file = input.files?.[0];
    const label = document.getElementById("artifact-file-name");
    if (label) label.textContent = file ? `${file.name} · ${sizeText(file.size)}` : "选择本地文件";
    if (inspect) inspect.disabled = !file || file.size > MAX_BYTES;
    const state = document.getElementById("artifact-upload-state");
    if (state && file?.size > MAX_BYTES) {
      state.textContent = "拒绝：文件超过 32 MiB";
      state.className = "artifact-upload-state error";
    } else if (state) {
      state.textContent = file ? "已选择 · 等待静态检查" : "等待文件";
      state.className = "artifact-upload-state";
    }
  });
  inspect?.addEventListener("click", uploadArtifact);
  document.getElementById("artifact-refresh")?.addEventListener("click", () => refreshList().catch(() => {}));
  refreshList().catch(error => {
    const list = document.getElementById("artifact-list");
    if (list) list.innerHTML = `<div class="artifact-empty error">读取失败：${esc(error.message || error)}</div>`;
  });
})();
