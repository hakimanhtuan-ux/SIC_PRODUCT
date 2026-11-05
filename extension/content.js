(() => {
  if (window.__TRUECHECK_CONTENT_INITIALIZED__) return;
  window.__TRUECHECK_CONTENT_INITIALIZED__ = true;

  const VERDICT_UI = {
    SUPPORTED: {
      icon: "🟢",
      label: "ĐƯỢC BẰNG CHỨNG HỖ TRỢ",
      bg: "#ecfdf5",
      border: "#6ee7b7",
      color: "#065f46",
    },
    REFUTED: {
      icon: "🔴",
      label: "CÓ BẰNG CHỨNG BÁC BỎ",
      bg: "#fef2f2",
      border: "#fca5a5",
      color: "#991b1b",
    },
    MISLEADING: {
      icon: "🟠",
      label: "THIẾU NGỮ CẢNH / DỄ HIỂU NHẦM",
      bg: "#fff7ed",
      border: "#fdba74",
      color: "#9a3412",
    },
    INSUFFICIENT_EVIDENCE: {
      icon: "🟡",
      label: "CHƯA ĐỦ BẰNG CHỨNG",
      bg: "#fefce8",
      border: "#fde047",
      color: "#854d0e",
    },
    CONFLICTING_EVIDENCE: {
      icon: "🔵",
      label: "BẰNG CHỨNG MÂU THUẪN",
      bg: "#f0f9ff",
      border: "#7dd3fc",
      color: "#075985",
    },
    NOT_VERIFIABLE: {
      icon: "⚪",
      label: "KHÔNG THỂ KIỂM CHỨNG KHÁCH QUAN",
      bg: "#f8fafc",
      border: "#cbd5e1",
      color: "#334155",
    },
  };

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Create Shadow DOM host so host page CSS never conflicts with TrueCheck UI
  const host = document.createElement("div");
  host.id = "truecheck-ai-extension-root";
  host.style.cssText =
    "all: initial; position: fixed; z-index: 2147483647; pointer-events: none; top: 0; left: 0; width: 0; height: 0;";
  document.documentElement.appendChild(host);

  const shadow = host.attachShadow({ mode: "open" });

  const styleEl = document.createElement("style");
  styleEl.textContent = `
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .tc-trigger-btn {
      pointer-events: auto;
      position: fixed;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #0f172a;
      color: #ffffff;
      border: 1px solid #334155;
      border-radius: 999px;
      padding: 7px 13px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 10px 25px rgba(15, 23, 42, 0.28);
      transition: transform 0.15s ease, background 0.15s ease;
      user-select: none;
    }
    .tc-trigger-btn:hover {
      background: #4338ca;
      transform: translateY(-1px);
    }
    .tc-card {
      pointer-events: auto;
      position: fixed;
      top: 20px;
      right: 20px;
      width: 390px;
      max-width: calc(100vw - 32px);
      max-height: calc(100vh - 40px);
      display: flex;
      flex-direction: column;
      background: #ffffff;
      color: #0f172a;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      box-shadow: 0 20px 45px rgba(15, 23, 42, 0.22);
      overflow: hidden;
    }
    .tc-header {
      background: #0f172a;
      color: #ffffff;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .tc-brand {
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.03em;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .tc-close {
      background: transparent;
      border: none;
      color: #94a3b8;
      font-size: 16px;
      cursor: pointer;
      padding: 2px 6px;
      border-radius: 6px;
    }
    .tc-close:hover { color: #ffffff; background: #1e293b; }
    .tc-body {
      padding: 14px 16px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 11px;
      font-size: 13px;
      line-height: 1.5;
    }
    .tc-verdict-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 11px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 12px;
      border: 1px solid transparent;
    }
    .tc-row-label {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #64748b;
      margin-bottom: 3px;
    }
    .tc-quote {
      background: #f8fafc;
      border-left: 3px solid #6366f1;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 12.5px;
      color: #1e293b;
      max-height: 88px;
      overflow-y: auto;
    }
    .tc-missing-box {
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 10px;
      padding: 8px 11px;
      font-size: 12px;
      color: #78350f;
    }
    .tc-missing-box ul {
      margin: 4px 0 0 16px;
      padding: 0;
    }
    .tc-manip-box {
      background: #eef2ff;
      border: 1px solid #c7d2fe;
      border-radius: 10px;
      padding: 8px 11px;
      font-size: 11.5px;
      color: #312e81;
    }
    .tc-source-item {
      border: 1px solid #e2e8f0;
      border-radius: 9px;
      padding: 8px 10px;
      margin-top: 6px;
      background: #f8fafc;
      font-size: 12px;
    }
    .tc-source-item a {
      color: #4338ca;
      font-weight: 600;
      text-decoration: none;
      display: block;
      margin-bottom: 3px;
    }
    .tc-source-item a:hover { text-decoration: underline; }
    .tc-tier-pill {
      display: inline-block;
      background: #0f172a;
      color: #fff;
      font-size: 10px;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 4px;
      margin-right: 5px;
    }
    .tc-footer {
      border-top: 1px solid #e2e8f0;
      padding: 10px 16px;
      background: #f8fafc;
      display: flex;
      gap: 8px;
      justify-content: space-between;
    }
    .tc-btn-secondary, .tc-btn-primary {
      flex: 1;
      text-align: center;
      padding: 7px 10px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      border: 1px solid transparent;
    }
    .tc-btn-secondary {
      background: #ffffff;
      color: #334155;
      border-color: #cbd5e1;
    }
    .tc-btn-primary {
      background: #4338ca;
      color: #ffffff;
    }
    .tc-btn-primary:hover { background: #3730a3; }
    .tc-spinner {
      width: 18px;
      height: 18px;
      border: 2.5px solid #e2e8f0;
      border-top-color: #4338ca;
      border-radius: 50%;
      animation: tcspin 0.75s linear infinite;
    }
    @keyframes tcspin { to { transform: rotate(360deg); } }
  `;
  shadow.appendChild(styleEl);

  let triggerBtn = null;
  let cardEl = null;
  let currentSelectedText = "";

  function removeTrigger() {
    if (triggerBtn) {
      triggerBtn.remove();
      triggerBtn = null;
    }
  }

  function removeCard() {
    if (cardEl) {
      cardEl.remove();
      cardEl = null;
    }
  }

  function showLoadingCard(selectedText) {
    removeTrigger();
    removeCard();
    cardEl = document.createElement("div");
    cardEl.className = "tc-card";
    cardEl.innerHTML = `
      <div class="tc-header">
        <div class="tc-brand">🛡️ TRUECHECK AI</div>
        <button class="tc-close" title="Đóng">✕</button>
      </div>
      <div class="tc-body">
        <div style="display:flex; align-items:center; gap:10px; padding:8px 0;">
          <div class="tc-spinner"></div>
          <div>
            <div style="font-weight:700;">Đang kiểm chứng mệnh đề & đối chiếu nguồn...</div>
            <div style="font-size:11.5px; color:#64748b;">Truy xuất bằng chứng đa tầng (Cấp 1–5)</div>
          </div>
        </div>
        <div>
          <div class="tc-row-label">Nội dung đang kiểm tra</div>
          <div class="tc-quote">${escapeHtml(selectedText)}</div>
        </div>
      </div>
    `;
    cardEl.querySelector(".tc-close").addEventListener("click", removeCard);
    shadow.appendChild(cardEl);
  }

  function showErrorCard(selectedText, errorMsg) {
    removeCard();
    cardEl = document.createElement("div");
    cardEl.className = "tc-card";
    cardEl.innerHTML = `
      <div class="tc-header">
        <div class="tc-brand">🛡️ TRUECHECK AI</div>
        <button class="tc-close" title="Đóng">✕</button>
      </div>
      <div class="tc-body">
        <div style="background:#fef2f2; border:1px solid #fecaca; color:#991b1b; padding:10px; border-radius:10px; font-size:12.5px;">
          <b>Không thể hoàn tất kiểm chứng:</b><br/>
          ${escapeHtml(errorMsg)}
        </div>
        <div>
          <div class="tc-row-label">Nội dung đã chọn</div>
          <div class="tc-quote">${escapeHtml(selectedText)}</div>
        </div>
      </div>
    `;
    cardEl.querySelector(".tc-close").addEventListener("click", removeCard);
    shadow.appendChild(cardEl);
  }

  function showResultCard(payload, webAppUrl) {
    removeCard();
    const claim = (payload.claims && payload.claims[0]) || null;
    if (!claim) {
      showErrorCard(payload.full_text, "Không trích xuất được mệnh đề cần kiểm chứng.");
      return;
    }

    const vStyle = VERDICT_UI[claim.verdict] || VERDICT_UI.INSUFFICIENT_EVIDENCE;
    const allSupp = claim.supporting_evidence || [];
    const allRef = claim.refuting_evidence || [];
    const allCtx = claim.contextual_evidence || [];
    const totalEv = allSupp.length + allRef.length + allCtx.length;
    const suppPct = totalEv > 0 ? Math.round((allSupp.length / totalEv) * 100) : 0;
    const refPct = totalEv > 0 ? Math.round((allRef.length / totalEv) * 100) : 0;
    const ctxPct = totalEv > 0 ? Math.max(0, 100 - suppPct - refPct) : 0;
    const compPct = Math.round((claim.evidence_completeness || 0) * 100);
    const pieGradient =
      totalEv > 0
        ? `conic-gradient(#059669 0% ${suppPct}%, #dc2626 ${suppPct}% ${suppPct + refPct
        }%, #6366f1 ${suppPct + refPct}% 100%)`
        : "#e2e8f0";
    const elapsedSec = ((payload.processing_time_ms || 0) / 1000).toFixed(2);
    const allSources = [...allSupp, ...allRef, ...allCtx].slice(0, 4);

    const missingHtml =
      claim.missing_information && claim.missing_information.length > 0
        ? `
          <div class="tc-missing-box">
            <b>Thông tin còn thiếu cần làm rõ:</b>
            <ul>
              ${claim.missing_information.map((m) => `<li>${escapeHtml(m)}</li>`).join("")}
            </ul>
          </div>
        `
        : "";

    const manipHtml =
      payload.manipulation_signals && payload.manipulation_signals.length > 0
        ? `
          <div class="tc-manip-box">
            <b>Tín hiệu ngôn từ (Độc lập dữ kiện):</b>
            ${payload.manipulation_signals
          .map((s) => escapeHtml(s.label_vi))
          .join(", ")}
          </div>
        `
        : "";

    const sourcesHtml =
      allSources.length > 0
        ? allSources
          .map(
            (ev) => `
              <div class="tc-source-item">
                <a href="${escapeHtml(ev.url)}" target="_blank" rel="noopener noreferrer">
                  <span class="tc-tier-pill">Cấp ${escapeHtml(ev.tier)}</span>
                  ${escapeHtml(ev.title)}
                </a>
                <div style="color:#475569; font-size:11px;">
                  ${escapeHtml(ev.domain)} • ${ev.citation_validated ? "✓ Đã xác thực trích dẫn" : "Đối chiếu ngữ cảnh"
              }
                </div>
              </div>
            `
          )
          .join("")
        : `<div style="font-size:12px; color:#64748b;">Chưa tìm thấy nguồn trực tiếp công khai.</div>`;

    const studioDeepLink = `${(webAppUrl || "http://localhost:3000").replace(
      /\/$/,
      ""
    )}/?claim=${encodeURIComponent(
      claim.original_text || payload.full_text
    )}&url=${encodeURIComponent(window.location.href)}`;

    cardEl = document.createElement("div");
    cardEl.className = "tc-card";
    cardEl.innerHTML = `
      <div class="tc-header">
        <div class="tc-brand">🛡️ TRUECHECK AI</div>
        <button class="tc-close" title="Đóng">✕</button>
      </div>
      <div class="tc-body">
        <div style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
          <span class="tc-verdict-badge" style="background:${vStyle.bg}; border-color:${vStyle.border}; color:${vStyle.color};">
            <span>${vStyle.icon}</span>
            <span>${escapeHtml(vStyle.label)}</span>
          </span>
          <span style="font-size:11px; font-weight:700; color:#64748b;">⚡ ${elapsedSec}s</span>
        </div>

        <div style="display:flex; align-items:center; gap:12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:9px 11px;">
          <div style="width:46px; height:46px; border-radius:50%; background:${pieGradient}; flex-shrink:0; display:flex; align-items:center; justify-content:center;">
            <div style="width:24px; height:24px; border-radius:50%; background:#ffffff; font-size:9.5px; font-weight:800; color:#0f172a; display:flex; align-items:center; justify-content:center;">
              ${compPct}%
            </div>
          </div>
          <div style="font-size:11.5px; line-height:1.45; flex:1;">
            <div style="font-weight:700; color:#0f172a;">Tương quan nguồn (%) • Độ đầy đủ ${compPct}%</div>
            <div style="color:#475569; margin-top:2px;">
              🟢 Ủng hộ <b>${suppPct}%</b> • 🔴 Bác bỏ <b>${refPct}%</b> • 🟣 Ngữ cảnh <b>${ctxPct}%</b>
            </div>
          </div>
        </div>

        <div>
          <div class="tc-row-label">Nội dung kiểm tra</div>
          <div class="tc-quote">${escapeHtml(claim.original_text)}</div>
        </div>

        <div>
          <div class="tc-row-label">Kết quả phân tích</div>
          <div style="color:#1e293b;">${escapeHtml(claim.explanation)}</div>
        </div>

        ${missingHtml}
        ${manipHtml}

        <div id="tc-evidence-section">
          <div class="tc-row-label">Nguồn tham khảo (${allSources.length})</div>
          ${sourcesHtml}
        </div>
      </div>
      <div class="tc-footer">
        <button type="button" class="tc-btn-secondary" id="tc-scroll-ev">Xem bằng chứng</button>
        <a href="${escapeHtml(studioDeepLink)}" target="_blank" rel="noopener noreferrer" class="tc-btn-primary">
          Kiểm chứng chuyên sâu ↗
        </a>
      </div>
    `;

    cardEl.querySelector(".tc-close").addEventListener("click", removeCard);
    cardEl.querySelector("#tc-scroll-ev").addEventListener("click", () => {
      const evSec = cardEl.querySelector("#tc-evidence-section");
      if (evSec) evSec.scrollIntoView({ behavior: "smooth" });
    });
    shadow.appendChild(cardEl);
  }

  function triggerVerification(text) {
    showLoadingCard(text);
    chrome.runtime.sendMessage(
      {
        type: "TRUECHECK_VERIFY_TEXT",
        text,
        contextUrl: window.location.href,
        contextTitle: document.title,
      },
      (res) => {
        if (chrome.runtime.lastError) {
          showErrorCard(text, chrome.runtime.lastError.message);
          return;
        }
        if (res && res.ok) {
          showResultCard(res.data, res.webAppUrl);
        } else {
          showErrorCard(text, (res && res.error) || "Lỗi không xác định.");
        }
      }
    );
  }

  // Listen to text selection (Highlight to Verify - P0)
  document.addEventListener("mouseup", (event) => {
    setTimeout(() => {
      const sel = window.getSelection();
      const text = sel ? sel.toString().trim() : "";
      if (text.length < 10 || text.length > 4000) {
        removeTrigger();
        return;
      }

      currentSelectedText = text;
      removeTrigger();

      let left = Math.min(window.innerWidth - 230, Math.max(12, event.clientX - 40));
      let top = Math.min(window.innerHeight - 48, Math.max(12, event.clientY + 14));
      try {
        const range = sel.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        if (rect && (rect.width > 0 || rect.height > 0)) {
          left = Math.min(window.innerWidth - 230, Math.max(12, rect.left));
          top = Math.min(window.innerHeight - 48, Math.max(12, rect.bottom + 8));
        }
      } catch (_) {
        // fallback to mouse coordinates
      }

      triggerBtn = document.createElement("button");
      triggerBtn.type = "button";
      triggerBtn.className = "tc-trigger-btn";
      triggerBtn.style.left = `${left}px`;
      triggerBtn.style.top = `${top}px`;
      triggerBtn.textContent = "🔍 Kiểm chứng với TrueCheck AI";
      triggerBtn.addEventListener("mousedown", (e) => {
        e.preventDefault();
        e.stopPropagation();
        triggerVerification(currentSelectedText);
      });
      shadow.appendChild(triggerBtn);
    }, 20);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      removeTrigger();
      removeCard();
    }
  });

  // Listen to Context Menu triggers from background.js
  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg) return;
    if (msg.type === "TRUECHECK_SHOW_LOADING") {
      showLoadingCard(msg.text);
    } else if (msg.type === "TRUECHECK_SHOW_RESULT") {
      showResultCard(msg.payload, msg.webAppUrl);
    } else if (msg.type === "TRUECHECK_SHOW_ERROR") {
      showErrorCard(msg.text, msg.error);
    }
  });
})();

