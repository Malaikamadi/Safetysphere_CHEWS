/**
 * CHEWS v3.0 — Global Health Assistant
 * Injects a floating Health Assistant button + slide-in chat panel on every page.
 * Talks to the multilingual /poc/ask endpoint.
 */
(function () {
  const API = (typeof window !== "undefined" && window.CHEWS_API) || "http://127.0.0.1:8000";

  const SUGGESTIONS = [
    "How to prevent malaria?",
    "Cholera signs",
    "Heat illness",
    "Flood safety",
    "Air quality",
  ];

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function mount() {
    if (document.getElementById("ha-fab")) return;

    const fab = document.createElement("button");
    fab.className = "ha-fab";
    fab.id = "ha-fab";
    fab.type = "button";
    fab.setAttribute("aria-label", "Open Health Assistant");
    fab.setAttribute("title", "Health Assistant");
    fab.innerHTML = `
      <span class="ha-fab__icon"><i data-lucide="message-square"></i></span>
      <span class="ha-fab__label">Health Assistant</span>
      <span class="ha-fab__pulse" aria-hidden="true"></span>
    `;

    const backdrop = document.createElement("div");
    backdrop.className = "ha-backdrop";
    backdrop.id = "ha-backdrop";
    backdrop.setAttribute("aria-hidden", "true");

    const panel = document.createElement("div");
    panel.className = "ha-panel";
    panel.id = "ha-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-labelledby", "ha-title");
    panel.setAttribute("aria-hidden", "true");
    panel.innerHTML = `
      <div class="ha-panel__header">
        <div class="ha-panel__brand">
          <div class="ha-panel__icon"><i data-lucide="sparkles"></i></div>
          <div>
            <div class="ha-panel__title" id="ha-title">Health Assistant</div>
            <div class="ha-panel__sub">Multilingual · Climate &amp; Health</div>
          </div>
        </div>
        <div class="ha-panel__actions">
          <select class="ha-lang" id="ha-lang" aria-label="Language">
            <option value="en">English</option>
            <option value="kri">Krio</option>
            <option value="fr">Français</option>
          </select>
          <button class="ha-close" id="ha-close" type="button" aria-label="Close">&times;</button>
        </div>
      </div>
      <div class="ha-panel__body" id="ha-body" aria-live="polite">
        <div class="ha-msg ha-msg--bot">
          Hi! I am the CHEWS Health Assistant. Ask me about malaria, cholera, flood safety,
          heat illness, air quality, or prevention.
          <div class="ha-suggestions" id="ha-suggestions"></div>
        </div>
      </div>
      <form class="ha-panel__footer" id="ha-form" autocomplete="off">
        <input type="text" class="ha-input" id="ha-input" placeholder="Ask a question..." />
        <button class="ha-send" id="ha-send" type="submit" aria-label="Send">
          <i data-lucide="send"></i>
        </button>
      </form>
    `;

    document.body.appendChild(backdrop);
    document.body.appendChild(panel);
    document.body.appendChild(fab);

    const suggestions = panel.querySelector("#ha-suggestions");
    SUGGESTIONS.forEach((q) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "ha-chip";
      chip.textContent = q;
      chip.addEventListener("click", () => {
        panel.querySelector("#ha-input").value = q;
        submit();
      });
      suggestions.appendChild(chip);
    });

    if (window.lucide) window.lucide.createIcons();

    wire();
  }

  function open() {
    document.getElementById("ha-panel").classList.add("is-open");
    document.getElementById("ha-backdrop").classList.add("is-open");
    document.getElementById("ha-panel").setAttribute("aria-hidden", "false");
    setTimeout(() => {
      const i = document.getElementById("ha-input");
      if (i) i.focus();
    }, 200);
  }

  function close() {
    document.getElementById("ha-panel").classList.remove("is-open");
    document.getElementById("ha-backdrop").classList.remove("is-open");
    document.getElementById("ha-panel").setAttribute("aria-hidden", "true");
  }

  function appendMsg(text, role) {
    const body = document.getElementById("ha-body");
    const msg = document.createElement("div");
    msg.className = "ha-msg " + (role === "user" ? "ha-msg--user" : "ha-msg--bot");
    msg.textContent = text;
    body.appendChild(msg);
    body.scrollTop = body.scrollHeight;
    return msg;
  }

  async function submit() {
    const inputEl = document.getElementById("ha-input");
    const sendBtn = document.getElementById("ha-send");
    const q = (inputEl.value || "").trim();
    if (!q) return;

    appendMsg(q, "user");
    inputEl.value = "";
    sendBtn.disabled = true;

    const thinking = appendMsg("Thinking…", "bot");
    thinking.classList.add("ha-msg--thinking");

    try {
      const language = document.getElementById("ha-lang").value || "en";
      const res = await fetch(`${API}/poc/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, language }),
      });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const data = await res.json();
      thinking.classList.remove("ha-msg--thinking");
      thinking.textContent = data.answer || "(no answer)";
    } catch (err) {
      thinking.classList.remove("ha-msg--thinking");
      thinking.textContent =
        "Sorry, I cannot reach the assistant right now. Is the backend running on port 8000?";
    } finally {
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  function wire() {
    document.getElementById("ha-fab").addEventListener("click", () => {
      const panel = document.getElementById("ha-panel");
      panel.classList.contains("is-open") ? close() : open();
    });
    document.getElementById("ha-close").addEventListener("click", close);
    document.getElementById("ha-backdrop").addEventListener("click", close);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && document.getElementById("ha-panel").classList.contains("is-open")) close();
    });
    document.getElementById("ha-form").addEventListener("submit", (e) => {
      e.preventDefault();
      submit();
    });
  }

  ready(mount);
})();
