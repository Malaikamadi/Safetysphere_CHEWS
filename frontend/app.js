/**
 * CHEWS v3.0 — Core Application Logic
 * Handles command center, malaria prediction, health assistant, system status, navigation.
 */

const API_BASE = "http://127.0.0.1:8000";

// ==================== DOM References ====================
const predictForm   = document.getElementById("predict-form");
const btnPredict    = document.getElementById("btn-predict");
const btnLoader     = document.getElementById("btn-loader");
const btnText       = document.getElementById("btn-text");
const resultSection = document.getElementById("result-section");
const gaugeArc      = document.getElementById("gauge-arc");
const gaugeValue    = document.getElementById("gauge-value");
const riskBadge     = document.getElementById("risk-badge");
const modelCards    = document.getElementById("model-cards");
const explanationText = document.getElementById("explanation-text");
const factorsList   = document.getElementById("factors-list");
const recsLi        = document.getElementById("recommendations-list");
const btnReset      = document.getElementById("btn-reset");
const btnAsk        = document.getElementById("btn-ask");
const askInput      = document.getElementById("ask-input");
const askAnswer     = document.getElementById("ask-answer");
const askAnswerText = document.getElementById("ask-answer-text");

let latestRiskScore = null;

// ==================== Mobile Menu ====================
const menuToggle = document.getElementById("menu-toggle");
const sidebar = document.getElementById("sidebar");
if (menuToggle && sidebar) {
  menuToggle.addEventListener("click", () => sidebar.classList.toggle("sidebar--open"));
  document.addEventListener("click", (e) => {
    if (sidebar.classList.contains("sidebar--open") && !sidebar.contains(e.target) && e.target !== menuToggle) {
      sidebar.classList.remove("sidebar--open");
    }
  });
}

// ==================== System Health Check ====================
async function checkHealth() {
  const statusEl = document.getElementById("api-status");
  const versionEl = document.getElementById("api-version");
  const modelsEl = document.getElementById("api-models");
  const areasEl = document.getElementById("api-areas");
  
  if (!statusEl) return;
  
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    statusEl.innerHTML = '<span style="color:var(--success)">● Online</span>';
    versionEl.textContent = data.version || "3.0.0";
    modelsEl.textContent = (data.models || []).length + " active";
    areasEl.textContent = (data.areas || []).length + " areas";
  } catch {
    statusEl.innerHTML = '<span style="color:var(--danger)">● Offline</span>';
    versionEl.textContent = "—";
    modelsEl.textContent = "—";
    areasEl.textContent = "—";
  }
}
checkHealth();

// ==================== Predict Form ====================
if (predictForm) {
  predictForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      rainfall: parseFloat(document.getElementById("rainfall").value),
      temperature: parseFloat(document.getElementById("temperature").value),
      humidity: parseFloat(document.getElementById("humidity").value),
      reported_cases: parseInt(document.getElementById("reported_cases").value, 10),
      trend: document.getElementById("trend").value,
      vulnerable_population: parseInt(document.getElementById("vulnerable_population").value || "0", 10),
      exposure_level: document.getElementById("exposure_level").value,
    };

    if ([payload.rainfall, payload.temperature, payload.humidity, payload.reported_cases].some(v => isNaN(v))) {
      alert("Please fill in all required fields.");
      return;
    }

    btnText.textContent = "Analysing…";
    btnLoader.classList.remove("hidden");
    btnPredict.disabled = true;

    try {
      const res = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const data = await res.json();
      latestRiskScore = data.final_risk;
      showResults(data);
      updateMetric("metric-malaria", data.final_risk.toFixed(2));
    } catch (err) {
      alert("Error: " + err.message + "\n\nMake sure the backend is running on port 8000.");
    } finally {
      btnText.textContent = "Run Risk Assessment";
      btnLoader.classList.add("hidden");
      btnPredict.disabled = false;
    }
  });
}

// ==================== Display Results ====================
function showResults(data) {
  resultSection.classList.remove("hidden");
  resultSection.classList.add("slide-up");

  const maxDash = 251;
  setTimeout(() => {
    gaugeArc.setAttribute("stroke-dasharray", `${data.final_risk * maxDash} ${maxDash}`);
  }, 50);
  animateCounter(gaugeValue, 0, data.final_risk, 1200);

  riskBadge.textContent = data.risk_level;
  riskBadge.className = "risk-badge risk-badge--" + data.risk_level.toLowerCase();

  renderModelCards(data.breakdown);
  explanationText.textContent = data.explanation;

  factorsList.innerHTML = "";
  data.factors.forEach(f => {
    const li = document.createElement("li");
    li.textContent = f;
    factorsList.appendChild(li);
  });
  if (window.lucide) lucide.createIcons();

  recsLi.innerHTML = "";
  data.recommendations.forEach(r => {
    const li = document.createElement("li");
    li.textContent = r;
    recsLi.appendChild(li);
  });
  if (window.lucide) lucide.createIcons();
}

function renderModelCards(breakdown) {
  modelCards.innerHTML = "";
  const models = [
    { key: "environmental", icon: "<i data-lucide="globe"></i>", name: "Environmental", color: "var(--accent)", weight: "40%" },
    { key: "epidemiological", icon: "<i data-lucide="bar-chart-2"></i>", name: "Epidemiological", color: "var(--warning)", weight: "40%" },
    { key: "exposure", icon: "<i data-lucide="users"></i>", name: "Exposure", color: "var(--purple)", weight: "20%" },
  ];
  models.forEach(m => {
    const d = breakdown[m.key];
    if (!d) return;
    const card = document.createElement("div");
    card.className = "model-card";
    card.innerHTML = `
      <div class="model-card__icon">${m.icon}</div>
      <div class="model-card__name">${m.name}</div>
      <div class="model-card__score" style="color:${m.color}">${d.score.toFixed(2)}</div>
      <div class="model-card__bar"><div class="model-card__fill" style="width:0%;background:${m.color}"></div></div>
      <div class="model-card__weight">Weight: ${m.weight}</div>
    `;
    modelCards.appendChild(card);
    if (window.lucide) lucide.createIcons();
    setTimeout(() => card.querySelector(".model-card__fill").style.width = `${d.score * 100}%`, 100);
  });
}

function animateCounter(el, from, to, duration) {
  const start = performance.now();
  function tick(now) {
    const p = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = (from + (to - from) * eased).toFixed(2);
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function updateMetric(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

// ==================== Reset ====================
if (btnReset) {
  btnReset.addEventListener("click", () => {
    resultSection.classList.add("hidden");
    if (gaugeArc) gaugeArc.setAttribute("stroke-dasharray", "0 251");
    if (gaugeValue) gaugeValue.textContent = "0.00";
    if (predictForm) predictForm.reset();
  });
}

// ==================== Ask Assistant ====================
if (btnAsk) {
  btnAsk.addEventListener("click", askQuestion);
  askInput.addEventListener("keydown", (e) => { if (e.key === "Enter") askQuestion(); });
}

async function askQuestion() {
  const question = askInput.value.trim();
  if (!question) return;
  askAnswer.classList.remove("hidden");
  askAnswerText.textContent = "Thinking…";
  try {
    const body = { question };
    if (latestRiskScore !== null) body.risk_score = latestRiskScore;
    const res = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data = await res.json();
    askAnswerText.textContent = data.answer;
  } catch {
    askAnswerText.textContent = "Could not reach the assistant. Is the backend running?";
  }
}
