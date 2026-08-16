(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);

  function clickProxy(selector, unavailableMessage) {
    const source = $(selector);
    if (!source || source.disabled) {
      const toast = $("#toast");
      if (toast) {
        toast.textContent = unavailableMessage;
        toast.className = "toast show error";
        setTimeout(() => { toast.className = "toast"; }, 2600);
      }
      return;
    }
    source.click();
  }

  function setDisabled(selector, disabled) {
    const button = $(selector);
    if (button && button.disabled !== disabled) button.disabled = disabled;
  }

  function syncDeck() {
    const newMission = $("#new-mission-btn") || $("#empty-new-mission-btn");
    const resume = $("#resume-btn");
    const approve = $("#approve-btn");
    const evidence = $("#evidence-btn");
    const retry = $("#retry-btn");

    setDisabled("#deck-new-mission", !newMission || newMission.disabled);
    setDisabled("#deck-resume", !resume || resume.disabled);
    setDisabled("#deck-approve", !approve || approve.disabled);
    setDisabled("#deck-evidence", !evidence || evidence.disabled);
    setDisabled("#deck-retry", !retry || retry.disabled);

    const target = $("#mission-target")?.textContent?.trim();
    const missionState = $("#mission-state")?.textContent?.trim();
    const current = $("#deck-current");
    if (current) {
      const text = target && target !== "—"
        ? `${target} · ${missionState && missionState !== "—" ? missionState : "unknown"}`
        : "尚無任務";
      if (current.textContent !== text) current.textContent = text;
    }
  }

  $("#deck-new-mission")?.addEventListener("click", () => clickProxy("#new-mission-btn, #empty-new-mission-btn", "目前無法建立任務。"));
  $("#deck-refresh")?.addEventListener("click", () => clickProxy("#refresh-btn", "刷新控制目前不可用。"));
  $("#deck-resume")?.addEventListener("click", () => clickProxy("#resume-btn", "目前任務不在可續行狀態。"));
  $("#deck-approve")?.addEventListener("click", () => clickProxy("#approve-btn", "目前沒有等待人工批准的步驟。"));
  $("#deck-evidence")?.addEventListener("click", () => clickProxy("#evidence-btn", "目前任務沒有可查看的證據。"));
  $("#deck-retry")?.addEventListener("click", () => clickProxy("#retry-btn", "目前任務不是可重跑的失敗狀態。"));

  $("#deck-scope-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const deckInput = $("#deck-scope-input");
    const sourceInput = $("#scope-input");
    const sourceForm = $("#scope-form");
    const value = deckInput?.value?.trim();
    if (!value || !sourceInput || !sourceForm) return;
    sourceInput.value = value;
    sourceForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    deckInput.value = "";
  });

  const observer = new MutationObserver(syncDeck);
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["disabled", "class"]
  });

  document.addEventListener("visibilitychange", syncDeck);
  window.addEventListener("focus", syncDeck);
  syncDeck();
})();
