const VERDICT_DOT = {
  SUPPORTED: "🟢",
  REFUTED: "🔴",
  MISLEADING: "🟠",
  INSUFFICIENT_EVIDENCE: "🟡",
  CONFLICTING_EVIDENCE: "🔵",
  NOT_VERIFIABLE: "⚪",
};

function escapeText(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

document.addEventListener("DOMContentLoaded", async () => {
  const quickText = document.getElementById("quick-text");
  const verifyBtn = document.getElementById("verify-btn");
  const quickResult = document.getElementById("quick-result");
  const saveHistoryToggle = document.getElementById("save-history-toggle");
  const clearHistoryBtn = document.getElementById("clear-history-btn");
  const historyList = document.getElementById("history-list");
  const apiUrlInput = document.getElementById("api-url");
  const webUrlInput = document.getElementById("web-url");
  const saveSettingsBtn = document.getElementById("save-settings-btn");
  const openStudioBtn = document.getElementById("open-studio-btn");

  const stored = await chrome.storage.local.get({
    apiBaseUrl: "http://localhost:8000",
    webAppUrl: "http://localhost:3000",
    saveHistory: false,
    verificationHistory: [],
  });

  apiUrlInput.value = stored.apiBaseUrl;
  webUrlInput.value = stored.webAppUrl;
  saveHistoryToggle.checked = Boolean(stored.saveHistory);

  function renderHistory(items) {
    if (!items || items.length === 0) {
      historyList.innerHTML = `<div style="font-size:11px; color:#94a3b8;">Chưa có lịch sử lưu trữ.</div>`;
      return;
    }
    historyList.innerHTML = items
      .slice(0, 8)
      .map(
        (h) => `
        <div class="history-item">
          <div><b>${VERDICT_DOT[h.verdict] || "🟡"} ${escapeText(h.verdictLabelVi)}</b></div>
          <div style="color:#475569;">${escapeText(h.text.slice(0, 90))}${
            h.text.length > 90 ? "..." : ""
          }</div>
        </div>
      `
      )
      .join("");
  }

  renderHistory(stored.verificationHistory);

  openStudioBtn.addEventListener("click", () => {
    const target = (webUrlInput.value || "http://localhost:3000").replace(/\/$/, "");
    chrome.tabs.create({ url: target });
  });

  saveHistoryToggle.addEventListener("change", async () => {
    await chrome.storage.local.set({ saveHistory: saveHistoryToggle.checked });
  });

  clearHistoryBtn.addEventListener("click", async () => {
    await chrome.storage.local.set({ verificationHistory: [] });
    renderHistory([]);
  });

  saveSettingsBtn.addEventListener("click", async () => {
    await chrome.storage.local.set({
      apiBaseUrl: apiUrlInput.value.trim() || "http://localhost:8000",
      webAppUrl: webUrlInput.value.trim() || "http://localhost:3000",
    });
    saveSettingsBtn.textContent = "✓ Đã lưu cấu hình";
    setTimeout(() => {
      saveSettingsBtn.textContent = "Lưu cấu hình";
    }, 1500);
  });

  verifyBtn.addEventListener("click", () => {
    const text = quickText.value.trim();
    if (text.length < 5) return;

    verifyBtn.disabled = true;
    verifyBtn.textContent = "Đang kiểm chứng...";
    quickResult.classList.remove("hidden");
    quickResult.innerHTML = "Đang truy xuất và xác thực bằng chứng...";

    chrome.runtime.sendMessage(
      {
        type: "TRUECHECK_VERIFY_TEXT",
        text,
        contextUrl: null,
        contextTitle: "TrueCheck Extension Popup",
      },
      async (res) => {
        verifyBtn.disabled = false;
        verifyBtn.textContent = "🔍 Kiểm chứng với TrueCheck AI";

        if (!res || !res.ok) {
          quickResult.innerHTML = `<span style="color:#b91c1c;">${escapeText(
            (res && res.error) || "Lỗi kết nối Backend (:8000)"
          )}</span>`;
          return;
        }

        const claim = res.data.claims && res.data.claims[0];
        if (!claim) {
          quickResult.textContent = "Không phát hiện mệnh đề cần kiểm chứng.";
          return;
        }

        const dot = VERDICT_DOT[claim.verdict] || "🟡";
        quickResult.innerHTML = `
          <div style="font-weight:700; margin-bottom:4px;">${dot} ${escapeText(
            claim.verdict_label_vi
          )}</div>
          <div>${escapeText(claim.explanation)}</div>
        `;

        const latest = await chrome.storage.local.get({ verificationHistory: [] });
        renderHistory(latest.verificationHistory);
      }
    );
  });
});

