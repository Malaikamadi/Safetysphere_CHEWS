/**
 * CHEWS v4.0 — CHW Mobile Dashboard
 */

const API_BASE = "http://localhost:8000";

// ==================== Tab Navigation ====================
function initTabs() {
  const tabs = document.querySelectorAll(".chw-tabbar__item");
  const contents = document.querySelectorAll(".chw-tab-content");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;

      tabs.forEach(t => t.classList.remove("chw-tabbar__item--active"));
      tab.classList.add("chw-tabbar__item--active");

      contents.forEach(c => {
        c.classList.remove("chw-tab-content--active");
        if (c.id === `chw-tab-${target}`) {
          c.classList.add("chw-tab-content--active");
        }
      });
    });
  });
}

// ==================== Report Form ====================
function initReportForm() {
  const form = document.getElementById("chw-report-form");
  if (!form) return;

  // Report type toggle
  document.querySelectorAll(".chw-toggle[data-rtype]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chw-toggle[data-rtype]").forEach(b => b.classList.remove("chw-toggle--active"));
      btn.classList.add("chw-toggle--active");
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector(".chw-submit-btn");
    const original = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Submitting...';
    submitBtn.disabled = true;

    // Simulate submission
    setTimeout(() => {
      submitBtn.innerHTML = '<i data-lucide="check"></i> Report Submitted!';
      submitBtn.classList.add("chw-submit-btn--success");
      
      setTimeout(() => {
        submitBtn.innerHTML = original;
        submitBtn.disabled = false;
        submitBtn.classList.remove("chw-submit-btn--success");
        form.reset();
        if (window.lucide) lucide.createIcons();
      }, 2000);

      if (window.lucide) lucide.createIcons();
    }, 1500);

    if (window.lucide) lucide.createIcons();
  });
}

// ==================== Triage Form ====================
function initTriageForm() {
  const form = document.getElementById("chw-triage-form");
  const result = document.getElementById("chw-triage-result");
  if (!form || !result) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector(".chw-submit-btn--triage");
    submitBtn.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Analyzing...';
    submitBtn.disabled = true;
    if (window.lucide) lucide.createIcons();

    // Simulate AI analysis
    setTimeout(() => {
      result.classList.add("chw-ai-result--visible");
      submitBtn.innerHTML = '<i data-lucide="search"></i> Analyze Symptoms';
      submitBtn.disabled = false;
      if (window.lucide) lucide.createIcons();
    }, 1500);
  });
}

// ==================== Chat Assistant ====================
function initChat() {
  const form = document.getElementById("chw-chat-form");
  const input = document.getElementById("chw-chat-input");
  const body = document.getElementById("chw-chat-body");
  if (!form || !input || !body) return;

  // Suggestion chips
  document.querySelectorAll(".chw-suggestion-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      input.value = chip.dataset.q;
      submitChat();
    });
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitChat();
  });

  async function submitChat() {
    const q = (input.value || "").trim();
    if (!q) return;

    // Add user message
    const userMsg = document.createElement("div");
    userMsg.className = "chw-chat-msg chw-chat-msg--user";
    userMsg.innerHTML = `<div class="chw-chat-msg__bubble">${escapeHtml(q)}</div>`;
    body.appendChild(userMsg);
    input.value = "";
    body.scrollTop = body.scrollHeight;

    // Add thinking indicator
    const thinking = document.createElement("div");
    thinking.className = "chw-chat-msg chw-chat-msg--bot";
    thinking.innerHTML = `
      <div class="chw-chat-msg__avatar"><i data-lucide="sparkles"></i></div>
      <div class="chw-chat-msg__bubble chw-chat-msg__bubble--thinking">Thinking…</div>
    `;
    body.appendChild(thinking);
    body.scrollTop = body.scrollHeight;
    if (window.lucide) lucide.createIcons();

    try {
      const res = await fetch(`${API_BASE}/poc/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, language: "en" }),
      });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const data = await res.json();
      thinking.querySelector(".chw-chat-msg__bubble").textContent = data.answer || "(no answer)";
      thinking.querySelector(".chw-chat-msg__bubble").classList.remove("chw-chat-msg__bubble--thinking");
    } catch (err) {
      thinking.querySelector(".chw-chat-msg__bubble").textContent =
        "Sorry, I can't reach the assistant right now. Check your connection.";
      thinking.querySelector(".chw-chat-msg__bubble").classList.remove("chw-chat-msg__bubble--thinking");
    }
    body.scrollTop = body.scrollHeight;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ==================== Profile Setup ====================
function initProfile() {
  const roleDetails = typeof getRoleDetails !== "undefined" ? getRoleDetails() : null;
  if (roleDetails) {
    const avatarEl = document.getElementById("chw-avatar");
    const nameEl = document.getElementById("chw-name");
    if (avatarEl) avatarEl.textContent = roleDetails.initials;
    if (nameEl) nameEl.textContent = roleDetails.fullName;
  }

  const district = typeof getDistrict !== "undefined" ? getDistrict() : null;
  const locEl = document.getElementById("chw-location");
  if (locEl && district) locEl.textContent = district;
}

// ==================== Init ====================
document.addEventListener("DOMContentLoaded", () => {
  initProfile();
  initTabs();
  initReportForm();
  initTriageForm();
  initChat();
});
