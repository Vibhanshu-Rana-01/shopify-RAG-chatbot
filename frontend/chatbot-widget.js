/**
 * Mobile Covers Chatbot Widget
 * ────────────────────────────
 * Self-contained floating chat widget for Shopify stores.
 * No external dependencies — pure vanilla JS + CSS injected at runtime.
 *
 * SETUP: Replace CHATBOT_CONFIG values below, then paste this entire
 * script inside your Shopify theme (Theme Editor → Edit Code →
 * layout/theme.liquid → before the closing </body> tag).
 *
 * Or add it via Settings → Custom Code → Footer.
 */

(function () {
  "use strict";

  /* ═══════════════════════════════════════════════════════════
     ▌ CONFIGURATION — Edit these values for your store
     ═══════════════════════════════════════════════════════════ */
  const CHATBOT_CONFIG = {
    apiUrl:         "http://localhost:8000",   // ← Your backend URL (local or Render.com)
    storeName:      "Mobile Covers",           // ← Your store display name
    welcomeMessage: "Hey there! 👋 I'm your personal shopping assistant.\n\nAsk me anything — which cover fits your phone, features, pricing, shipping, or anything else!",
    placeholder:    "Ask me anything about our covers...",
    primaryColor:   "#7C3AED",    // Purple — main brand color
    accentColor:    "#A855F7",    // Lighter purple
    gradientStart:  "#7C3AED",
    gradientEnd:    "#EC4899",    // Pink gradient for header
    botAvatar:      "🛍️",
    quickQuestions: [
      "What covers do you have for iPhone 15?",
      "What's your return policy?",
      "Do you offer free shipping?",
      "What materials are your covers made of?",
    ],
  };
  /* ═══════════════════════════════════════════════════════════ */

  // State
  let isOpen        = false;
  let isTyping      = false;
  let chatHistory   = [];  // [{role, content}]
  let hasGreeted    = false;

  // ─── Inject Styles ───────────────────────────────────────────

  const STYLES = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    #mcb-root * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    /* ── Launcher Button ── */
    #mcb-launcher {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9998;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, ${CHATBOT_CONFIG.gradientStart}, ${CHATBOT_CONFIG.gradientEnd});
      border: none;
      cursor: pointer;
      box-shadow: 0 8px 32px rgba(124, 58, 237, 0.45);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
      outline: none;
    }
    #mcb-launcher:hover {
      transform: scale(1.1);
      box-shadow: 0 12px 40px rgba(124, 58, 237, 0.6);
    }
    #mcb-launcher:active { transform: scale(0.95); }

    #mcb-launcher svg { transition: transform 0.3s ease, opacity 0.3s ease; }
    #mcb-launcher .mcb-icon-chat   { position: absolute; }
    #mcb-launcher .mcb-icon-close  { position: absolute; opacity: 0; transform: rotate(-90deg); }
    #mcb-launcher.mcb-open .mcb-icon-chat  { opacity: 0; transform: rotate(90deg); }
    #mcb-launcher.mcb-open .mcb-icon-close { opacity: 1; transform: rotate(0deg); }

    /* Notification badge */
    #mcb-badge {
      position: absolute;
      top: -2px;
      right: -2px;
      width: 18px;
      height: 18px;
      background: #EF4444;
      border-radius: 50%;
      border: 2px solid white;
      font-size: 10px;
      font-weight: 700;
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      animation: mcb-pulse 2s infinite;
    }
    @keyframes mcb-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
      50%       { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
    }

    /* ── Chat Window ── */
    #mcb-window {
      position: fixed;
      bottom: 96px;
      right: 24px;
      z-index: 9999;
      width: 380px;
      max-width: calc(100vw - 32px);
      height: 580px;
      max-height: calc(100vh - 120px);
      border-radius: 24px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      background: #0F0F1A;
      box-shadow:
        0 32px 80px rgba(0,0,0,0.5),
        0 0 0 1px rgba(255,255,255,0.06),
        inset 0 1px 0 rgba(255,255,255,0.08);
      transform: translateY(20px) scale(0.95);
      opacity: 0;
      pointer-events: none;
      transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    #mcb-window.mcb-visible {
      transform: translateY(0) scale(1);
      opacity: 1;
      pointer-events: all;
    }

    /* ── Header ── */
    #mcb-header {
      background: linear-gradient(135deg, ${CHATBOT_CONFIG.gradientStart}, ${CHATBOT_CONFIG.gradientEnd});
      padding: 18px 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
      position: relative;
      overflow: hidden;
    }
    #mcb-header::before {
      content: '';
      position: absolute;
      top: -50%;
      right: -20%;
      width: 200px;
      height: 200px;
      background: rgba(255,255,255,0.07);
      border-radius: 50%;
    }
    #mcb-avatar {
      width: 44px;
      height: 44px;
      background: rgba(255,255,255,0.2);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      flex-shrink: 0;
      backdrop-filter: blur(10px);
      border: 1.5px solid rgba(255,255,255,0.25);
    }
    #mcb-header-info { flex: 1; }
    #mcb-header-name {
      font-size: 15px;
      font-weight: 700;
      color: white;
      letter-spacing: -0.2px;
    }
    #mcb-header-status {
      font-size: 12px;
      color: rgba(255,255,255,0.8);
      display: flex;
      align-items: center;
      gap: 5px;
      margin-top: 2px;
    }
    #mcb-header-status::before {
      content: '';
      width: 7px;
      height: 7px;
      background: #4ADE80;
      border-radius: 50%;
      box-shadow: 0 0 6px #4ADE80;
      animation: mcb-blink 2s infinite;
    }
    @keyframes mcb-blink {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.4; }
    }
    #mcb-sync-btn {
      background: rgba(255,255,255,0.15);
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 8px;
      padding: 6px 10px;
      color: white;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      backdrop-filter: blur(10px);
      transition: background 0.2s;
      white-space: nowrap;
    }
    #mcb-sync-btn:hover { background: rgba(255,255,255,0.25); }

    /* ── Messages Area ── */
    #mcb-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }
    #mcb-messages::-webkit-scrollbar { width: 4px; }
    #mcb-messages::-webkit-scrollbar-track { background: transparent; }
    #mcb-messages::-webkit-scrollbar-thumb {
      background: rgba(255,255,255,0.1);
      border-radius: 2px;
    }

    /* ── Message Bubbles ── */
    .mcb-msg {
      display: flex;
      gap: 8px;
      animation: mcb-fadeUp 0.3s ease;
    }
    @keyframes mcb-fadeUp {
      from { opacity: 0; transform: translateY(10px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .mcb-msg.mcb-user  { flex-direction: row-reverse; }
    .mcb-msg.mcb-bot   { flex-direction: row; }

    .mcb-msg-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      flex-shrink: 0;
      align-self: flex-end;
    }
    .mcb-msg.mcb-bot .mcb-msg-avatar {
      background: linear-gradient(135deg, ${CHATBOT_CONFIG.gradientStart}, ${CHATBOT_CONFIG.gradientEnd});
    }
    .mcb-msg.mcb-user .mcb-msg-avatar {
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.1);
    }

    .mcb-bubble {
      max-width: 78%;
      padding: 12px 16px;
      border-radius: 18px;
      font-size: 14px;
      line-height: 1.55;
      word-break: break-word;
    }
    .mcb-msg.mcb-user .mcb-bubble {
      background: linear-gradient(135deg, ${CHATBOT_CONFIG.gradientStart}, ${CHATBOT_CONFIG.gradientEnd});
      color: white;
      border-bottom-right-radius: 4px;
    }
    .mcb-msg.mcb-bot .mcb-bubble {
      background: rgba(255,255,255,0.06);
      color: #E5E7EB;
      border-bottom-left-radius: 4px;
      border: 1px solid rgba(255,255,255,0.06);
    }
    .mcb-bubble a {
      color: ${CHATBOT_CONFIG.accentColor};
      text-decoration: underline;
    }

    /* ── Typing Indicator ── */
    #mcb-typing {
      display: flex;
      gap: 8px;
      align-items: center;
      animation: mcb-fadeUp 0.3s ease;
    }
    #mcb-typing .mcb-msg-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: linear-gradient(135deg, ${CHATBOT_CONFIG.gradientStart}, ${CHATBOT_CONFIG.gradientEnd});
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
    }
    .mcb-dots {
      display: flex;
      gap: 4px;
      padding: 12px 16px;
      background: rgba(255,255,255,0.06);
      border-radius: 18px;
      border-bottom-left-radius: 4px;
      border: 1px solid rgba(255,255,255,0.06);
    }
    .mcb-dot {
      width: 7px;
      height: 7px;
      background: rgba(255,255,255,0.35);
      border-radius: 50%;
      animation: mcb-bounce 1.2s infinite;
    }
    .mcb-dot:nth-child(2) { animation-delay: 0.2s; }
    .mcb-dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes mcb-bounce {
      0%, 80%, 100% { transform: translateY(0); background: rgba(255,255,255,0.35); }
      40%            { transform: translateY(-6px); background: ${CHATBOT_CONFIG.accentColor}; }
    }

    /* ── Quick Questions ── */
    #mcb-quick-wrap {
      padding: 8px 16px 0;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .mcb-quick-btn {
      background: rgba(124, 58, 237, 0.15);
      border: 1px solid rgba(124, 58, 237, 0.3);
      border-radius: 20px;
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 500;
      color: ${CHATBOT_CONFIG.accentColor};
      cursor: pointer;
      transition: all 0.2s ease;
      white-space: nowrap;
    }
    .mcb-quick-btn:hover {
      background: rgba(124, 58, 237, 0.3);
      border-color: ${CHATBOT_CONFIG.accentColor};
      transform: translateY(-1px);
    }

    /* ── Input Area ── */
    #mcb-input-area {
      padding: 12px 16px;
      background: rgba(255,255,255,0.03);
      border-top: 1px solid rgba(255,255,255,0.06);
      display: flex;
      gap: 10px;
      align-items: flex-end;
      flex-shrink: 0;
    }
    #mcb-input {
      flex: 1;
      background: rgba(255,255,255,0.07);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 14px;
      padding: 11px 15px;
      font-size: 14px;
      color: #F3F4F6;
      outline: none;
      resize: none;
      min-height: 44px;
      max-height: 120px;
      line-height: 1.4;
      transition: border-color 0.2s;
      font-family: inherit;
    }
    #mcb-input::placeholder { color: rgba(255,255,255,0.3); }
    #mcb-input:focus { border-color: ${CHATBOT_CONFIG.primaryColor}; }

    #mcb-send {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: linear-gradient(135deg, ${CHATBOT_CONFIG.gradientStart}, ${CHATBOT_CONFIG.gradientEnd});
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s;
      box-shadow: 0 4px 12px rgba(124, 58, 237, 0.4);
    }
    #mcb-send:hover { transform: scale(1.08); box-shadow: 0 6px 16px rgba(124,58,237,0.55); }
    #mcb-send:active { transform: scale(0.95); }
    #mcb-send:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

    /* ── Powered by ── */
    #mcb-footer {
      text-align: center;
      padding: 6px 0 10px;
      font-size: 10px;
      color: rgba(255,255,255,0.2);
      flex-shrink: 0;
    }

    /* ── Mobile ── */
    @media (max-width: 480px) {
      #mcb-window {
        bottom: 0;
        right: 0;
        width: 100vw;
        height: 90vh;
        max-height: 90vh;
        border-radius: 24px 24px 0 0;
      }
      #mcb-launcher { bottom: 16px; right: 16px; }
    }
  `;

  // ─── DOM Builders ────────────────────────────────────────────

  function createRoot() {
    const style = document.createElement("style");
    style.id = "mcb-styles";
    style.textContent = STYLES;
    document.head.appendChild(style);

    const root = document.createElement("div");
    root.id = "mcb-root";
    document.body.appendChild(root);
    return root;
  }

  function createLauncher(root) {
    const btn = document.createElement("button");
    btn.id = "mcb-launcher";
    btn.setAttribute("aria-label", "Open chat");
    btn.innerHTML = `
      <svg class="mcb-icon-chat" width="26" height="26" fill="none" viewBox="0 0 24 24">
        <path fill="white" d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2ZM8 11H7a1 1 0 0 1 0-2h1a1 1 0 0 1 0 2Zm5 0h-2a1 1 0 0 1 0-2h2a1 1 0 0 1 0 2Zm4 0h-1a1 1 0 0 1 0-2h1a1 1 0 0 1 0 2Z"/>
      </svg>
      <svg class="mcb-icon-close" width="22" height="22" fill="none" viewBox="0 0 24 24">
        <path stroke="white" stroke-width="2.5" stroke-linecap="round" d="M6 6l12 12M6 18L18 6"/>
      </svg>
      <span id="mcb-badge">1</span>
    `;
    root.appendChild(btn);
    return btn;
  }

  function createWindow(root) {
    const win = document.createElement("div");
    win.id = "mcb-window";
    win.setAttribute("role", "dialog");
    win.setAttribute("aria-label", "Chat with us");
    win.innerHTML = `
      <div id="mcb-header">
        <div id="mcb-avatar">${CHATBOT_CONFIG.botAvatar}</div>
        <div id="mcb-header-info">
          <div id="mcb-header-name">${CHATBOT_CONFIG.storeName} Assistant</div>
          <div id="mcb-header-status">Online — here to help</div>
        </div>
        <button id="mcb-sync-btn" title="Refresh product catalog">⟳ Refresh</button>
      </div>

      <div id="mcb-messages"></div>

      <div id="mcb-quick-wrap">
        ${CHATBOT_CONFIG.quickQuestions
          .map(q => `<button class="mcb-quick-btn" data-question="${q}">${q}</button>`)
          .join("")}
      </div>

      <div id="mcb-input-area">
        <textarea
          id="mcb-input"
          placeholder="${CHATBOT_CONFIG.placeholder}"
          rows="1"
          maxlength="800"
        ></textarea>
        <button id="mcb-send" aria-label="Send message">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
            <path fill="white" d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
      <div id="mcb-footer">Powered by AI • ${CHATBOT_CONFIG.storeName}</div>
    `;
    root.appendChild(win);
    return win;
  }

  // ─── Message Rendering ───────────────────────────────────────

  function appendMessage(role, content) {
    const messagesEl = document.getElementById("mcb-messages");

    const msgEl = document.createElement("div");
    msgEl.classList.add("mcb-msg", role === "user" ? "mcb-user" : "mcb-bot");

    // Convert newlines and basic markdown links to HTML
    const formatted = content
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/\n/g, "<br>");

    msgEl.innerHTML = `
      <div class="mcb-msg-avatar">${role === "user" ? "👤" : CHATBOT_CONFIG.botAvatar}</div>
      <div class="mcb-bubble">${formatted}</div>
    `;

    messagesEl.appendChild(msgEl);
    scrollToBottom();
  }

  function showTyping() {
    const messagesEl = document.getElementById("mcb-messages");
    const typingEl   = document.createElement("div");
    typingEl.id = "mcb-typing";
    typingEl.innerHTML = `
      <div class="mcb-msg-avatar">${CHATBOT_CONFIG.botAvatar}</div>
      <div class="mcb-dots">
        <div class="mcb-dot"></div>
        <div class="mcb-dot"></div>
        <div class="mcb-dot"></div>
      </div>
    `;
    messagesEl.appendChild(typingEl);
    scrollToBottom();
  }

  function hideTyping() {
    const el = document.getElementById("mcb-typing");
    if (el) el.remove();
  }

  function scrollToBottom() {
    const el = document.getElementById("mcb-messages");
    if (el) el.scrollTop = el.scrollHeight;
  }

  function setInputDisabled(disabled) {
    const input  = document.getElementById("mcb-input");
    const sendBtn = document.getElementById("mcb-send");
    if (input)   input.disabled   = disabled;
    if (sendBtn) sendBtn.disabled = disabled;
  }

  // ─── API Call ────────────────────────────────────────────────

  async function sendMessageToAPI(userMessage) {
    isTyping = true;
    setInputDisabled(true);
    showTyping();

    try {
      const response = await fetch(`${CHATBOT_CONFIG.apiUrl}/chat`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          history: chatHistory.slice(-12),   // last 12 messages for context
        }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data       = await response.json();
      const botMessage = data.response || "Sorry, I couldn't process that. Please try again.";

      hideTyping();
      appendMessage("assistant", botMessage);

      // Add to history
      chatHistory.push({ role: "user",      content: userMessage });
      chatHistory.push({ role: "assistant", content: botMessage  });

    } catch (err) {
      hideTyping();
      const errMsg =
        err.message.includes("Failed to fetch")
          ? "I'm having trouble connecting right now. Please make sure the chatbot backend is running."
          : "Oops! Something went wrong. Please try again in a moment.";
      appendMessage("assistant", errMsg);
      console.error("[MCB] API error:", err);
    } finally {
      isTyping = false;
      setInputDisabled(false);
      document.getElementById("mcb-input")?.focus();
    }
  }

  async function triggerSync() {
    const btn = document.getElementById("mcb-sync-btn");
    if (!btn) return;
    btn.textContent = "Syncing...";
    btn.disabled    = true;
    try {
      const res  = await fetch(`${CHATBOT_CONFIG.apiUrl}/sync`, { method: "POST" });
      const data = await res.json();
      btn.textContent = `✓ ${data.products || 0} products`;
      setTimeout(() => { btn.textContent = "⟳ Refresh"; btn.disabled = false; }, 3000);
    } catch {
      btn.textContent = "⟳ Refresh";
      btn.disabled    = false;
    }
  }

  // ─── Toggle Open / Close ─────────────────────────────────────

  function openChat() {
    isOpen = true;
    document.getElementById("mcb-launcher").classList.add("mcb-open");
    document.getElementById("mcb-window").classList.add("mcb-visible");

    const badge = document.getElementById("mcb-badge");
    if (badge) badge.remove();

    // Show welcome message once
    if (!hasGreeted) {
      hasGreeted = true;
      setTimeout(() => {
        appendMessage("assistant", CHATBOT_CONFIG.welcomeMessage);
      }, 300);
    }

    setTimeout(() => document.getElementById("mcb-input")?.focus(), 350);
  }

  function closeChat() {
    isOpen = false;
    document.getElementById("mcb-launcher").classList.remove("mcb-open");
    document.getElementById("mcb-window").classList.remove("mcb-visible");
  }

  function toggleChat() {
    isOpen ? closeChat() : openChat();
  }

  // ─── Send Message Flow ───────────────────────────────────────

  function handleSend() {
    if (isTyping) return;
    const input = document.getElementById("mcb-input");
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    // Hide quick question chips after first message
    const quickWrap = document.getElementById("mcb-quick-wrap");
    if (quickWrap) quickWrap.style.display = "none";

    appendMessage("user", text);
    sendMessageToAPI(text);
  }

  // ─── Init ────────────────────────────────────────────────────

  function init() {
    const root      = createRoot();
    const launcher  = createLauncher(root);
    const chatWin   = createWindow(root);

    // Launcher toggle
    launcher.addEventListener("click", toggleChat);

    // Send button
    document.getElementById("mcb-send").addEventListener("click", handleSend);

    // Enter key to send (Shift+Enter = new line)
    document.getElementById("mcb-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    // Auto-resize textarea
    document.getElementById("mcb-input").addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });

    // Quick question chips
    document.getElementById("mcb-quick-wrap").addEventListener("click", function (e) {
      const btn = e.target.closest(".mcb-quick-btn");
      if (!btn || isTyping) return;
      const q = btn.dataset.question;
      if (!q) return;

      document.getElementById("mcb-quick-wrap").style.display = "none";
      appendMessage("user", q);
      sendMessageToAPI(q);
    });

    // Sync / refresh button
    document.getElementById("mcb-sync-btn").addEventListener("click", triggerSync);

    // Close on outside click
    document.addEventListener("click", function (e) {
      if (isOpen && !chatWin.contains(e.target) && !launcher.contains(e.target)) {
        closeChat();
      }
    });

    // Auto-open after 5 seconds on first visit (optional — remove if not wanted)
    if (!sessionStorage.getItem("mcb-seen")) {
      sessionStorage.setItem("mcb-seen", "1");
      setTimeout(openChat, 5000);
    }

    console.log("[MCB] Mobile Covers Chatbot widget loaded ✅");
  }

  // Bootstrap when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
