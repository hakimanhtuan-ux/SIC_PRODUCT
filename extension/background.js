const DEFAULT_SETTINGS = {
  apiBaseUrl: "http://localhost:8000",
  webAppUrl: "http://localhost:3000",
  saveHistory: false,
};

async function getSettings() {
  const stored = await chrome.storage.local.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...stored };
}

async function appendHistoryIfEnabled(entry) {
  const settings = await getSettings();
  if (!settings.saveHistory) return;
  const { verificationHistory = [] } = await chrome.storage.local.get({
    verificationHistory: [],
  });
  const next = [entry, ...verificationHistory].slice(0, 30);
  await chrome.storage.local.set({ verificationHistory: next });
}

async function callVerificationEngine({ text, contextUrl, contextTitle }) {
  const settings = await getSettings();
  const endpoint = `${settings.apiBaseUrl.replace(/\/$/, "")}/api/v1/verify/text`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      context_url: contextUrl || null,
      context_title: contextTitle || null,
      redact_pii: false,
      use_claim_memory: true,
    }),
  });

  if (!response.ok) {
    let errMsg = `Lỗi máy chủ TrueCheck (${response.status})`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errMsg = errJson.detail;
    } catch (_) {
      // ignore json parse error
    }
    throw new Error(errMsg);
  }

  const data = await response.json();
  const primaryClaim = data.claims && data.claims[0];
  if (primaryClaim) {
    await appendHistoryIfEnabled({
      id: data.document_id,
      text: primaryClaim.original_text || text,
      verdict: primaryClaim.verdict,
      verdictLabelVi: primaryClaim.verdict_label_vi,
      contextUrl: contextUrl || "",
      verifiedAt: data.verified_at,
    });
  }
  return { data, webAppUrl: settings.webAppUrl };
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "truecheck-verify-selection",
    title: "🔍 Kiểm chứng với TrueCheck AI",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (
    info.menuItemId !== "truecheck-verify-selection" ||
    !info.selectionText ||
    !tab ||
    !tab.id
  ) {
    return;
  }

  const selectedText = info.selectionText.trim();
  if (selectedText.length < 5) return;

  try {
    await chrome.tabs.sendMessage(tab.id, {
      type: "TRUECHECK_SHOW_LOADING",
      text: selectedText,
    });
    const { data, webAppUrl } = await callVerificationEngine({
      text: selectedText,
      contextUrl: info.pageUrl || tab.url,
      contextTitle: tab.title,
    });
    await chrome.tabs.sendMessage(tab.id, {
      type: "TRUECHECK_SHOW_RESULT",
      payload: data,
      webAppUrl,
    });
  } catch (err) {
    await chrome.tabs.sendMessage(tab.id, {
      type: "TRUECHECK_SHOW_ERROR",
      text: selectedText,
      error:
        err instanceof Error
          ? err.message
          : "Không thể kết nối Backend TrueCheck (:8000).",
    });
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.type === "TRUECHECK_VERIFY_TEXT") {
    callVerificationEngine({
      text: message.text,
      contextUrl: message.contextUrl,
      contextTitle: message.contextTitle,
    })
      .then((res) => sendResponse({ ok: true, ...res }))
      .catch((err) =>
        sendResponse({
          ok: false,
          error:
            err instanceof Error
              ? err.message
              : "Không thể kết nối tới TrueCheck AI Backend.",
        })
      );
    return true; // keep async message channel open
  }
  return false;
});

