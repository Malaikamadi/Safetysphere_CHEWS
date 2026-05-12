/**
 * CHEWS v3.0 — Point-of-Care Logic
 */
const API = "http://127.0.0.1:8000";

const mt = document.getElementById("menu-toggle"), sb = document.getElementById("sidebar");
if (mt && sb) { mt.addEventListener("click", () => sb.classList.toggle("sidebar--open")); }

function switchTab(tab) {
  document.querySelectorAll(".tab-content").forEach(t => t.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(b => { b.classList.remove("active-tab","btn--secondary"); b.classList.add("btn--ghost"); });
  document.getElementById("tab-" + tab).classList.remove("hidden");
  const btn = document.querySelector(`[data-tab="${tab}"]`);
  btn.classList.add("active-tab","btn--secondary"); btn.classList.remove("btn--ghost");
}

// === Triage ===
document.getElementById("triage-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const symptoms = Array.from(document.querySelectorAll('input[name="symptom"]:checked')).map(cb => cb.value);
  if (symptoms.length === 0) {
    alert("Please select at least one symptom.");
    return;
  }

  try {
    const res = await fetch(`${API}/poc/triage`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symptoms: symptoms,
        patient_group: document.getElementById("t-group").value,
        language: document.getElementById("t-lang").value,
        heat_risk: +document.getElementById("t-heat").value,
        air_quality_risk: +document.getElementById("t-aq").value,
        flood_risk: +document.getElementById("t-flood").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data = await res.json();
    renderTriage(data);
  } catch (err) { alert("Error: " + err.message); }
});

function renderTriage(data) {
  const el = document.getElementById("triage-result");
  el.classList.remove("hidden"); el.classList.add("slide-up");

  const cls = `triage-${data.urgency.toLowerCase()}`;
  const badgeCls = `risk-badge--${data.urgency.toLowerCase()}`;

  let html = `
    <div style="text-align:center;margin-bottom:1.5rem;padding:1.5rem;background:rgba(15,23,42,0.4);border-radius:12px;border:1px solid var(--border)">
      <div style="font-size:0.75rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim);margin-bottom:0.5rem">TRIAGE CATEGORY</div>
      <div class="risk-badge ${badgeCls}" style="font-size:1.1rem;padding:0.6rem 2rem;margin-bottom:1rem">${data.urgency.toUpperCase()} — ${data.category.toUpperCase()}</div>
      <p style="font-size:1.2rem;font-weight:700" class="${cls}">${data.assessment}</p>
    </div>
  `;

  if (data.referral_needed) {
    html += `
      <div class="result-panel result-panel--danger mb-1" style="background:rgba(239,68,68,0.1)">
        <div style="font-size:1rem;font-weight:700;color:var(--danger);display:flex;align-items:center;gap:0.5rem">
          <span><i data-lucide="ambulance"></i></span> REFERRAL REQUIRED
        </div>
        <p style="font-size:0.85rem;color:var(--text);margin-top:0.25rem">This patient requires immediate evaluation by a medical professional. Prepare for transport to the nearest health facility.</p>
      </div>
    `;
  }

  html += `
    <div class="mb-1">
      <div class="section-heading"><i data-lucide="thermometer"></i> Climate Context</div>
      <div class="result-panel result-panel--warning" style="padding:1rem">
        <p style="font-size:0.85rem">${data.climate_context}</p>
      </div>
    </div>
    
    <div class="mb-1">
      <div class="section-heading"><i data-lucide="clipboard-list"></i> Recommended Actions</div>
      <ul class="result-list ${data.referral_needed ? 'result-list--danger' : 'result-list--info'}">
        ${data.actions.map(a => `<li>${a}</li>`).join("")}
      </ul>
    </div>
  `;

  el.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// === Assistant ===
document.getElementById("btn-ask").addEventListener("click", askAssistant);
document.getElementById("a-input").addEventListener("keydown", e => { if (e.key === "Enter") askAssistant(); });

async function askAssistant() {
  const q = document.getElementById("a-input").value.trim();
  if (!q) return;

  const el = document.getElementById("ask-result");
  const textEl = document.getElementById("ask-text");
  
  el.classList.remove("hidden");
  textEl.textContent = "Thinking...";

  try {
    const res = await fetch(`${API}/poc/ask`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: q,
        language: document.getElementById("a-lang").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data = await res.json();
    textEl.textContent = data.answer;
  } catch (err) {
    textEl.textContent = "Error connecting to assistant: " + err.message;
  }
}
