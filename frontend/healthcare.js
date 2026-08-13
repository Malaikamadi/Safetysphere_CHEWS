/**
 * CHEWS v3.0 — Healthcare Readiness Logic
 */
const API = "/api";

const mt = document.getElementById("menu-toggle"), sb = document.getElementById("sidebar");
if (mt && sb) { mt.addEventListener("click", () => sb.classList.toggle("sidebar--open")); }

function switchTab(tab) {
  document.querySelectorAll(".tab-content").forEach(t => t.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(b => { b.classList.remove("active-tab", "btn--secondary"); b.classList.add("btn--ghost"); });
  document.getElementById("tab-" + tab).classList.remove("hidden");
  const btn = document.querySelector(`[data-tab="${tab}"]`);
  btn.classList.add("active-tab", "btn--secondary"); btn.classList.remove("btn--ghost");
}

// === Disease Forecast ===
document.getElementById("forecast-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await fetch(`${API}/healthcare/forecast`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        disease: document.getElementById("f-disease").value,
        current_month: +document.getElementById("f-month").value,
        rainfall: +document.getElementById("f-rain").value,
        temperature: +document.getElementById("f-temp").value,
        humidity: +document.getElementById("f-hum").value,
        current_cases: +document.getElementById("f-current").value,
        previous_cases: +document.getElementById("f-prev").value,
        aqi: +document.getElementById("f-aqi").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data = await res.json();
    renderForecast(data);
  } catch (err) { alert("Error: " + err.message); }
});

function renderForecast(data) {
  const el = document.getElementById("forecast-result");
  el.classList.remove("hidden"); el.classList.add("slide-up");

  const lvlClass = data.predicted_risk_level.toLowerCase().replace(/\s+/g, '-');
  const trendIcon = { Rising: `<i data-lucide="trending-up"></i>`, Stable: `<i data-lucide="arrow-right"></i>`, Declining: `<i data-lucide="trending-down"></i>` }[data.risk_trend] || `<i data-lucide="arrow-right"></i>`;
  const trendColor = { Rising: "var(--danger)", Stable: "var(--text-dim)", Declining: "var(--success)" }[data.risk_trend];

  el.innerHTML = `
    <div style="text-align:center;margin-bottom:1.25rem">
      <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim);margin-bottom:0.25rem">${data.disease.toUpperCase()} FORECAST</div>
      <div class="risk-badge risk-badge--${lvlClass}" style="font-size:0.9rem;padding:0.45rem 1.25rem">${data.predicted_risk_level}</div>
      <div style="font-size:0.72rem;color:var(--text-dim);margin-top:0.5rem">${data.forecast_period}</div>
    </div>

    <div class="grid-4 mb-1">
      <div class="metric">
        <div class="metric__icon">${trendIcon}</div>
        <div class="metric__label">Risk Trend</div>
        <div class="metric__value" style="color:${trendColor};font-size:1.1rem">${data.risk_trend}</div>
      </div>
      <div class="metric">
        <div class="metric__icon"><i data-lucide="crosshair"></i></div>
        <div class="metric__label">Onset Probability</div>
        <div class="metric__value" style="font-size:1.3rem">${(data.onset_likelihood * 100).toFixed(0)}%</div>
        <div class="progress-bar"><div class="progress-bar__fill" style="width:${data.onset_likelihood * 100}%;background:var(--accent-2)"></div></div>
      </div>
      <div class="metric">
        <div class="metric__icon"><i data-lucide="bar-chart-2"></i></div>
        <div class="metric__label">Surge Probability</div>
        <div class="metric__value" style="font-size:1.3rem;color:${data.surge_probability > 0.6 ? 'var(--danger)' : 'var(--warning)'}">${(data.surge_probability * 100).toFixed(0)}%</div>
        <div class="progress-bar"><div class="progress-bar__fill" style="width:${data.surge_probability * 100}%;background:linear-gradient(90deg,var(--warning),var(--danger))"></div></div>
      </div>
      <div class="metric">
        <div class="metric__icon"><i data-lucide="calendar"></i></div>
        <div class="metric__label">Peak Window</div>
        <div class="metric__value" style="font-size:1rem">${data.peak_window}</div>
        <div class="metric__trend">Confidence: ${(data.confidence * 100).toFixed(0)}%</div>
      </div>
    </div>

    <div class="mb-1"><div class="section-heading"><i data-lucide="zap"></i> Key Factors</div>
      <ul class="result-list result-list--warning">${data.factors.map(f => `<li>${f}</li>`).join("")}</ul>
    </div>
    <div class="mb-1"><div class="section-heading"><i data-lucide="check-circle"></i> Recommendations</div>
      <ul class="result-list result-list--success">${data.recommendations.map(r => `<li>${r}</li>`).join("")}</ul>
    </div>
  `;
}

// === Anomaly Detection ===
document.getElementById("anomaly-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await fetch(`${API}/healthcare/anomaly-detect`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pm25: +document.getElementById("a-pm25").value,
        pm10: +document.getElementById("a-pm10").value,
        expected_pm25: +document.getElementById("a-pm25-exp").value,
        expected_pm10: +document.getElementById("a-pm10-exp").value,
        temperature: +document.getElementById("a-temp").value,
        expected_temperature: +document.getElementById("a-temp-exp").value,
        location: document.getElementById("a-loc").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data = await res.json();
    renderAnomaly(data);
  } catch (err) { alert("Error: " + err.message); }
});

function renderAnomaly(data) {
  const el = document.getElementById("anomaly-result");
  el.classList.remove("hidden"); el.classList.add("slide-up");

  let html = `
    <div style="text-align:center;margin-bottom:1rem">
      <div style="font-size:2rem;font-weight:800;color:${data.anomalies_detected ? 'var(--danger)' : 'var(--success)'}">${data.anomalies_detected ? '<i data-lucide="alert-triangle"></i> ANOMALIES DETECTED' : '<i data-lucide="check-circle"></i> NO ANOMALIES'}</div>
      <div style="font-size:0.78rem;color:var(--text-dim)">${data.location} · AQI: ${data.current_aqi} (${data.current_category})</div>
    </div>`;

  if (data.anomalies.length) {
    html += `<div class="grid-${Math.min(data.anomalies.length, 3)} mb-1">`;
    data.anomalies.forEach(a => {
      html += `<div class="result-panel result-panel--danger">
        <div style="font-size:0.78rem;font-weight:700;color:var(--text-bright);margin-bottom:0.5rem">${a.parameter}</div>
        <div class="grid-2" style="gap:0.35rem;margin-bottom:0.5rem">
          <div style="font-size:0.72rem;color:var(--text-dim)">Observed</div><div style="font-size:0.85rem;font-weight:700;color:var(--danger)">${a.observed}</div>
          <div style="font-size:0.72rem;color:var(--text-dim)">Expected</div><div style="font-size:0.85rem;font-weight:700">${a.expected}</div>
          <div style="font-size:0.72rem;color:var(--text-dim)">Deviation</div><div style="font-size:0.85rem;font-weight:700;color:var(--warning)">${a.deviation_pct || a.deviation_celsius}${a.deviation_pct ? '%' : '°C'}</div>
          <div style="font-size:0.72rem;color:var(--text-dim)">Severity</div><div class="risk-badge risk-badge--${a.severity.toLowerCase()}" style="font-size:0.65rem">${a.severity}</div>
        </div>
        <div style="font-size:0.72rem;color:var(--text-dim)">Possible causes:</div>
        <ul style="margin-top:0.25rem;padding-left:1rem;font-size:0.75rem;color:var(--text)">${a.possible_causes.map(c => `<li>${c}</li>`).join("")}</ul>
      </div>`;
    });
    html += `</div>`;
  }

  html += `<div class="mb-1"><div class="section-heading"><i data-lucide="clipboard-list"></i> Actions</div>
    <ul class="result-list result-list--success">${data.recommendations.map(r => `<li>${r}</li>`).join("")}</ul>
  </div>`;

  el.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// === Surge Planning ===
document.getElementById("surge-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await fetch(`${API}/healthcare/surge-plan`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        disease: document.getElementById("s-disease").value,
        current_cases: +document.getElementById("s-current").value,
        forecast_surge_pct: +document.getElementById("s-surge").value,
        bed_capacity: +document.getElementById("s-beds").value,
        staff_available: +document.getElementById("s-staff").value,
        supply_days: +document.getElementById("s-supply").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data = await res.json();
    renderSurge(data);
  } catch (err) { alert("Error: " + err.message); }
});

function renderSurge(data) {
  const el = document.getElementById("surge-result");
  el.classList.remove("hidden"); el.classList.add("slide-up");

  const lvlColors = { Ready: "var(--success)", "Partially Ready": "var(--warning)", "At Risk": "var(--orange)", "Critical Gap": "var(--danger)" };
  const lvlColor = lvlColors[data.readiness_level] || "var(--text)";
  const lvlClass = data.readiness_level.toLowerCase().replace(/\s+/g, '-');

  el.innerHTML = `
    <div style="text-align:center;margin-bottom:1rem">
      <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim)">READINESS SCORE</div>
      <div style="font-size:2.5rem;font-weight:800;color:${lvlColor}">${(data.readiness_score * 100).toFixed(0)}%</div>
      <div class="risk-badge risk-badge--${lvlClass === 'critical-gap' ? 'critical' : lvlClass === 'at-risk' ? 'high' : lvlClass === 'partially-ready' ? 'moderate' : 'low'}">${data.readiness_level}</div>
    </div>
    <div class="progress-bar mb-1"><div class="progress-bar__fill" style="width:${data.readiness_score * 100}%;background:linear-gradient(90deg,var(--danger),var(--warning),var(--success))"></div></div>

    <div class="grid-3 mb-1">
      <div class="metric">
        <div class="metric__icon"><i data-lucide="bed"></i></div>
        <div class="metric__label">Bed Utilization</div>
        <div class="metric__value" style="color:${data.bed_utilization_pct > 80 ? 'var(--danger)' : 'var(--text-bright)'}">${data.bed_utilization_pct}%</div>
        <div class="metric__trend">${data.expected_surge_cases} expected vs ${data.current_cases} current</div>
      </div>
      <div class="metric">
        <div class="metric__icon"><i data-lucide="stethoscope"></i></div>
        <div class="metric__label">Staff:Patient Ratio</div>
        <div class="metric__value" style="color:${data.staff_patient_ratio < 0.3 ? 'var(--danger)' : 'var(--text-bright)'}">${data.staff_patient_ratio}</div>
      </div>
      <div class="metric">
        <div class="metric__icon"><i data-lucide="pill"></i></div>
        <div class="metric__label">Supply Days</div>
        <div class="metric__value" style="color:${data.supply_days_remaining < 14 ? 'var(--warning)' : 'var(--text-bright)'}">${data.supply_days_remaining}</div>
      </div>
    </div>

    <div class="mb-1"><div class="section-heading"><i data-lucide="alert-triangle"></i> Gaps Identified</div>
      <ul class="result-list result-list--danger">${data.gaps.map(g => `<li>${g}</li>`).join("")}</ul>
    </div>
    <div class="mb-1"><div class="section-heading"><i data-lucide="check-circle"></i> Recommendations</div>
      <ul class="result-list result-list--success">${data.recommendations.map(r => `<li>${r}</li>`).join("")}</ul>
    </div>
  `;
}

document.querySelectorAll("a.nav-link--soon").forEach((a) => a.addEventListener("click", (e) => e.preventDefault()));

// ═══════════════════════════════════════════════════════════════════
// ML Prediction Forms
// ═══════════════════════════════════════════════════════════════════

// --- Malaria Case Predictor ---
document.getElementById("ml-malaria-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await fetch(`${API}/healthcare/ml/malaria-predict`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        district: document.getElementById("ml-m-district").value,
        rainfall_mm: +document.getElementById("ml-m-rain").value,
        temperature_c: +document.getElementById("ml-m-temp").value,
        humidity_percent: +document.getElementById("ml-m-hum").value,
        water_stagnation_index: +document.getElementById("ml-m-stag").value,
        mosquito_breeding_sites: +document.getElementById("ml-m-breed").value,
        reported_fever_cases: +document.getElementById("ml-m-fever").value,
        population_density: +document.getElementById("ml-m-pop").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    renderMalariaResult(await res.json());
  } catch (err) { alert("Error: " + err.message); }
});

function renderMalariaResult(data) {
  const el = document.getElementById("ml-malaria-result");
  el.classList.remove("hidden"); el.classList.add("slide-up");
  const lvlColors = { Low: "var(--success)", Moderate: "var(--warning)", High: "var(--orange)", Critical: "var(--danger)" };
  const lvlColor = lvlColors[data.risk_level] || "var(--text)";
  const lvlClass = data.risk_level.toLowerCase();

  let contribHtml = "";
  if (data.feature_contributions && Object.keys(data.feature_contributions).length) {
    const sorted = Object.entries(data.feature_contributions).sort((a, b) => b[1] - a[1]).slice(0, 6);
    contribHtml = `<div class="zone-detail__bars" style="margin-top:0.75rem">` +
      sorted.map(([k, v]) => `<div class="contrib"><span class="contrib__lbl">${k.replace(/_/g, " ")}</span><div class="contrib__track"><div class="contrib__fill" style="width:${(v * 100).toFixed(0)}%;background:var(--accent-2)"></div></div><span class="contrib__val">${(v * 100).toFixed(0)}%</span></div>`).join("") +
      `</div>`;
  }

  el.innerHTML = `
    <div style="text-align:center;margin-bottom:1.25rem">
      <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim)">PREDICTED MALARIA CASES</div>
      <div style="font-size:3rem;font-weight:800;color:${lvlColor}">${data.predicted_cases}</div>
      <div class="risk-badge risk-badge--${lvlClass === 'critical' ? 'high' : lvlClass}" style="font-size:0.85rem;padding:0.4rem 1.2rem">${data.risk_level} Risk</div>
    </div>
    <div class="mb-1"><div class="section-heading"><i data-lucide="zap"></i> Contributing Factors</div>
      <ul class="result-list result-list--warning">${data.confidence_factors.map(f => `<li>${f}</li>`).join("")}</ul>
    </div>
    ${contribHtml ? `<div class="section-heading"><i data-lucide="bar-chart-2"></i> Feature Importances</div>${contribHtml}` : ""}
  `;
  if (window.lucide) lucide.createIcons();
}

// --- Healthcare Readiness Predictor ---
document.getElementById("ml-readiness-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await fetch(`${API}/healthcare/ml/readiness-predict`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        district: document.getElementById("ml-r-district").value,
        facility_type: document.getElementById("ml-r-type").value,
        beds_available: +document.getElementById("ml-r-beds").value,
        health_workers: +document.getElementById("ml-r-workers").value,
        malaria_medicine_stock: +document.getElementById("ml-r-medicine").value,
        power_availability: +document.getElementById("ml-r-power").value,
        water_availability: +document.getElementById("ml-r-water").value,
        patient_load: +document.getElementById("ml-r-load").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    renderReadinessResult(await res.json());
  } catch (err) { alert("Error: " + err.message); }
});

function renderReadinessResult(data) {
  const el = document.getElementById("ml-readiness-result");
  el.classList.remove("hidden"); el.classList.add("slide-up");
  const lvlColors = { Ready: "var(--success)", "Partially Ready": "var(--warning)", "Under-prepared": "var(--orange)", Critical: "var(--danger)" };
  const lvlColor = lvlColors[data.readiness_level] || "var(--text)";
  const pct = (data.readiness_score * 100).toFixed(0);

  let contribHtml = "";
  if (data.feature_contributions && Object.keys(data.feature_contributions).length) {
    const sorted = Object.entries(data.feature_contributions).sort((a, b) => b[1] - a[1]).slice(0, 6);
    contribHtml = `<div class="zone-detail__bars" style="margin-top:0.75rem">` +
      sorted.map(([k, v]) => `<div class="contrib"><span class="contrib__lbl">${k.replace(/_/g, " ")}</span><div class="contrib__track"><div class="contrib__fill" style="width:${(v * 100).toFixed(0)}%;background:var(--success)"></div></div><span class="contrib__val">${(v * 100).toFixed(0)}%</span></div>`).join("") +
      `</div>`;
  }

  el.innerHTML = `
    <div style="text-align:center;margin-bottom:1.25rem">
      <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim)">READINESS SCORE</div>
      <div style="font-size:3rem;font-weight:800;color:${lvlColor}">${pct}%</div>
      <div class="risk-badge risk-badge--${data.readiness_level === 'Ready' ? 'low' : data.readiness_level === 'Partially Ready' ? 'moderate' : 'high'}" style="font-size:0.85rem;padding:0.4rem 1.2rem">${data.readiness_level}</div>
    </div>
    <div class="progress-bar mb-1"><div class="progress-bar__fill" style="width:${pct}%;background:linear-gradient(90deg,var(--danger),var(--warning),var(--success))"></div></div>
    <div class="result-panel result-panel--info mb-1" style="text-align:center"><p style="font-size:0.85rem;margin:0">${data.capacity_assessment}</p></div>
    <div class="mb-1"><div class="section-heading"><i data-lucide="alert-triangle"></i> Key Gaps</div>
      <ul class="result-list result-list--danger">${data.key_gaps.map(g => `<li>${g}</li>`).join("")}</ul>
    </div>
    ${contribHtml ? `<div class="section-heading"><i data-lucide="bar-chart-2"></i> Feature Importances</div>${contribHtml}` : ""}
  `;
  if (window.lucide) lucide.createIcons();
}

// --- Community Flood Classifier ---
document.getElementById("ml-flood-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await fetch(`${API}/healthcare/ml/community-flood`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        district: document.getElementById("ml-f-district").value,
        community: document.getElementById("ml-f-community").value,
        standing_water: +document.getElementById("ml-f-water").value,
        fever_reports: +document.getElementById("ml-f-fever").value,
        damaged_houses: +document.getElementById("ml-f-houses").value,
        displaced_households: +document.getElementById("ml-f-displaced").value,
        water_contamination: +document.getElementById("ml-f-contam").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    renderFloodResult(await res.json());
  } catch (err) { alert("Error: " + err.message); }
});

function renderFloodResult(data) {
  const el = document.getElementById("ml-flood-result");
  el.classList.remove("hidden"); el.classList.add("slide-up");
  const alertColors = { Critical: "var(--danger)", Warning: "var(--orange)", Watch: "var(--warning)", Normal: "var(--success)" };
  const alertColor = alertColors[data.alert_level] || "var(--text)";
  const probPct = (data.flood_probability * 100).toFixed(0);

  let contribHtml = "";
  if (data.feature_contributions && Object.keys(data.feature_contributions).length) {
    const sorted = Object.entries(data.feature_contributions).sort((a, b) => b[1] - a[1]).slice(0, 6);
    contribHtml = `<div class="zone-detail__bars" style="margin-top:0.75rem">` +
      sorted.map(([k, v]) => `<div class="contrib"><span class="contrib__lbl">${k.replace(/_/g, " ")}</span><div class="contrib__track"><div class="contrib__fill" style="width:${(v * 100).toFixed(0)}%;background:var(--warning)"></div></div><span class="contrib__val">${(v * 100).toFixed(0)}%</span></div>`).join("") +
      `</div>`;
  }

  el.innerHTML = `
    <div style="text-align:center;margin-bottom:1.25rem">
      <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim)">FLOOD CLASSIFICATION</div>
      <div style="font-size:2.5rem;font-weight:800;color:${alertColor}">${data.flood_predicted ? "⚠️ FLOOD LIKELY" : "✅ NO FLOOD"}</div>
      <div class="risk-badge risk-badge--${data.alert_level === 'Critical' || data.alert_level === 'Warning' ? 'high' : data.alert_level === 'Watch' ? 'moderate' : 'low'}" style="font-size:0.85rem;padding:0.4rem 1.2rem">${data.alert_level}</div>
    </div>
    <div class="grid-2 mb-1">
      <div class="metric">
        <div class="metric__icon"><i data-lucide="percent"></i></div>
        <div class="metric__label">Flood Probability</div>
        <div class="metric__value" style="font-size:1.5rem;color:${alertColor}">${probPct}%</div>
        <div class="progress-bar"><div class="progress-bar__fill" style="width:${probPct}%;background:linear-gradient(90deg,var(--success),var(--warning),var(--danger))"></div></div>
      </div>
      <div class="metric">
        <div class="metric__icon"><i data-lucide="shield-alert"></i></div>
        <div class="metric__label">Alert Level</div>
        <div class="metric__value" style="font-size:1.5rem;color:${alertColor}">${data.alert_level}</div>
      </div>
    </div>
    <div class="mb-1"><div class="section-heading"><i data-lucide="zap"></i> Contributing Factors</div>
      <ul class="result-list result-list--warning">${data.contributing_factors.map(f => `<li>${f}</li>`).join("")}</ul>
    </div>
    ${contribHtml ? `<div class="section-heading"><i data-lucide="bar-chart-2"></i> Feature Importances</div>${contribHtml}` : ""}
  `;
  if (window.lucide) lucide.createIcons();
}

// ═══════════════════════════════════════════════════════════════════
// MFL Facility Explorer
// ═══════════════════════════════════════════════════════════════════

let mflMap = null;
let mflMarkers = null;
let mflFacilities = [];
let mflGeojson = null;
let mflMapInitialized = false;

// --- Load MFL Data ---
async function loadMflData() {
  try {
    const [summaryRes, facilitiesRes, qualityRes] = await Promise.all([
      fetch(`${API}/healthcare/facilities/summary`),
      fetch(`${API}/healthcare/facilities`),
      fetch(`${API}/healthcare/facilities/data-quality`),
    ]);

    if (summaryRes.ok) {
      const summary = await summaryRes.json();
      renderMflOverview(summary);
    }

    if (facilitiesRes.ok) {
      const data = await facilitiesRes.json();
      mflFacilities = data.facilities || [];
      renderMflTable(mflFacilities);
      initMflMap();
    }

    if (qualityRes.ok) {
      const quality = await qualityRes.json();
      renderDataQuality(quality);
    }
  } catch (err) {
    console.error("[MFL] Error loading facility data:", err);
  }
}

// --- Render National Overview ---
function renderMflOverview(summary) {
  const el = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
  el("mfl-total", summary.total_facilities);
  el("mfl-ready", (summary.by_readiness?.["Ready"] || 0) + (summary.by_readiness?.["Partially Ready"] || 0));
  el("mfl-underprepared", (summary.by_readiness?.["Under-prepared"] || 0) + (summary.by_readiness?.["Critical"] || 0));
  el("mfl-power-pct", summary.facilities_with_power_pct + "%");
  el("mfl-water-pct", summary.facilities_with_water_pct + "%");
  el("mfl-flood-exposed", summary.flood_exposed_facilities);
  if (window.lucide) lucide.createIcons();
}

// --- Initialize Leaflet Map ---
function initMflMap() {
  if (mflMapInitialized) { updateMflMapMarkers(); return; }
  const mapEl = document.getElementById("mfl-map");
  if (!mapEl || !window.L) return;

  mflMap = L.map("mfl-map", { zoomControl: true }).setView([8.46, -11.78], 7);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 18,
  }).addTo(mflMap);

  // Sierra Leone boundary
  fetch("sierra-leone-districts.geojson")
    .then(r => r.json())
    .then(geo => {
      L.geoJSON(geo, {
        style: { color: "rgba(255,255,255,0.2)", weight: 1, fillColor: "rgba(100,149,237,0.05)", fillOpacity: 0.3 },
      }).addTo(mflMap);
    })
    .catch(() => {});

  mflMarkers = L.layerGroup().addTo(mflMap);
  updateMflMapMarkers();
  mflMapInitialized = true;
}

function updateMflMapMarkers() {
  if (!mflMarkers || !mflMap) return;
  mflMarkers.clearLayers();

  const readinessColors = {
    "Ready": "#22c55e",
    "Partially Ready": "#f59e0b",
    "Under-prepared": "#f97316",
    "Critical": "#ef4444",
  };

  mflFacilities.forEach(f => {
    if (!f.latitude || !f.longitude) return;

    const color = readinessColors[f.readiness_level] || "#888";
    const radius = f.facility_type === "Tertiary" ? 8 : f.facility_type === "Secondary" ? 7 : 6;

    const marker = L.circleMarker([f.latitude, f.longitude], {
      radius: radius,
      fillColor: color,
      color: "rgba(255,255,255,0.4)",
      weight: 1,
      fillOpacity: 0.85,
    });

    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:200px">
        <div style="font-weight:700;font-size:0.85rem;margin-bottom:4px">${f.facility_name}</div>
        <div style="font-size:0.72rem;color:#888;margin-bottom:6px">${f.facility_id} · ${f.facility_type} · ${f.district}</div>
        <div style="display:flex;gap:6px;align-items:center;margin-bottom:4px">
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color}"></span>
          <span style="font-size:0.78rem;font-weight:600">${f.readiness_level} (${(f.readiness_score * 100).toFixed(0)}%)</span>
        </div>
        <div style="font-size:0.72rem;color:#aaa">
          Beds: ${f.beds_available} · Staff: ${f.health_workers} · Power: ${f.power_availability ? '✓' : '✗'} · Water: ${f.water_availability ? '✓' : '✗'}
        </div>
        <div style="font-size:0.65rem;color:#666;margin-top:4px;font-style:italic">${f.coord_source === 'approximate_district_centroid' ? '⚠ Approximate location' : 'DHIS2 coordinates'}</div>
        <button onclick="openFacilityProfile('${f.facility_id}')" style="margin-top:8px;padding:4px 12px;font-size:0.72rem;background:#6366f1;color:white;border:none;border-radius:4px;cursor:pointer">View Profile</button>
      </div>
    `);

    mflMarkers.addLayer(marker);
  });
}

// --- Render Facility Table ---
function renderMflTable(facilities) {
  const tbody = document.getElementById("mfl-table-body");
  const countEl = document.getElementById("mfl-table-count");
  if (!tbody) return;

  if (countEl) countEl.textContent = `Showing ${facilities.length} facilities`;

  if (facilities.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:2rem;color:var(--text-dim)">No facilities match the current filters</td></tr>';
    return;
  }

  const readinessColors = {
    "Ready": "#22c55e", "Partially Ready": "#f59e0b",
    "Under-prepared": "#f97316", "Critical": "#ef4444",
  };

  tbody.innerHTML = facilities.map(f => `
    <tr>
      <td style="font-family:monospace;font-size:0.72rem;color:var(--text-dim)">${f.facility_id}</td>
      <td style="font-weight:600">${f.facility_name}</td>
      <td>${f.district}</td>
      <td><span class="mfl-type-badge mfl-type-badge--${f.facility_type.toLowerCase()}">${f.facility_type}</span></td>
      <td>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${readinessColors[f.readiness_level] || '#888'}"></span>
          <span style="font-size:0.78rem">${(f.readiness_score * 100).toFixed(0)}%</span>
        </div>
      </td>
      <td>${f.beds_available}</td>
      <td>${f.health_workers}</td>
      <td>${f.power_availability ? '<span style="color:#22c55e">✓</span>' : '<span style="color:#ef4444">✗</span>'}</td>
      <td>${f.water_availability ? '<span style="color:#22c55e">✓</span>' : '<span style="color:#ef4444">✗</span>'}</td>
      <td><button class="btn btn--ghost btn--sm" onclick="openFacilityProfile('${f.facility_id}')" style="font-size:0.7rem;padding:0.2rem 0.6rem"><i data-lucide="eye" style="width:12px;height:12px"></i> View</button></td>
    </tr>
  `).join("");
  if (window.lucide) lucide.createIcons();
}

// --- Filters ---
function applyMflFilters() {
  const district = document.getElementById("mfl-district-filter").value;
  const type = document.getElementById("mfl-type-filter").value;
  const readiness = document.getElementById("mfl-readiness-filter").value;
  const search = document.getElementById("mfl-search").value.toLowerCase().trim();

  let filtered = mflFacilities;
  if (district) filtered = filtered.filter(f => f.district === district);
  if (type) filtered = filtered.filter(f => f.facility_type === type);
  if (readiness) filtered = filtered.filter(f => f.readiness_level === readiness);
  if (search) {
    filtered = filtered.filter(f =>
      f.facility_name.toLowerCase().includes(search) ||
      f.district.toLowerCase().includes(search) ||
      f.facility_id.toLowerCase().includes(search)
    );
  }

  renderMflTable(filtered);

  // Update map
  if (mflMarkers) {
    mflMarkers.clearLayers();
    const old = mflFacilities;
    mflFacilities = filtered;
    updateMflMapMarkers();
    mflFacilities = old;
  }

  const countEl = document.getElementById("mfl-filter-count");
  if (countEl) countEl.textContent = `${filtered.length} of ${mflFacilities.length} facilities`;
}

function resetMflFilters() {
  document.getElementById("mfl-district-filter").value = "";
  document.getElementById("mfl-type-filter").value = "";
  document.getElementById("mfl-readiness-filter").value = "";
  document.getElementById("mfl-search").value = "";
  renderMflTable(mflFacilities);
  updateMflMapMarkers();
  const countEl = document.getElementById("mfl-filter-count");
  if (countEl) countEl.textContent = "";
}

// Debounced search
let mflSearchTimeout;
const mflSearchInput = document.getElementById("mfl-search");
if (mflSearchInput) {
  mflSearchInput.addEventListener("input", () => {
    clearTimeout(mflSearchTimeout);
    mflSearchTimeout = setTimeout(applyMflFilters, 300);
  });
}

// --- Facility Profile Modal ---
async function openFacilityProfile(facilityId) {
  const overlay = document.getElementById("mfl-profile-overlay");
  const content = document.getElementById("mfl-profile-content");
  if (!overlay || !content) return;

  content.innerHTML = '<div style="text-align:center;padding:3rem;color:var(--text-dim)"><i data-lucide="loader" class="spin"></i> Loading facility profile…</div>';
  overlay.classList.remove("hidden");
  if (window.lucide) lucide.createIcons();

  try {
    const [profileRes, ewRes] = await Promise.all([
      fetch(`${API}/healthcare/facilities/${facilityId}`),
      fetch(`${API}/healthcare/facilities/${facilityId}/early-warning`),
    ]);

    if (!profileRes.ok) throw new Error("Facility not found");
    const profile = await profileRes.json();
    const earlyWarning = ewRes.ok ? await ewRes.json() : null;

    renderFacilityProfile(profile, earlyWarning);
  } catch (err) {
    content.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--danger)">Error: ${err.message}</div>`;
  }
}

function closeFacilityProfile() {
  const overlay = document.getElementById("mfl-profile-overlay");
  if (overlay) overlay.classList.add("hidden");
}

// Close on overlay click
document.getElementById("mfl-profile-overlay")?.addEventListener("click", (e) => {
  if (e.target.id === "mfl-profile-overlay") closeFacilityProfile();
});

// Close on Escape
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeFacilityProfile();
});

function renderFacilityProfile(profile, earlyWarning) {
  const content = document.getElementById("mfl-profile-content");
  if (!content) return;

  const readinessColors = {
    "Ready": "#22c55e", "Partially Ready": "#f59e0b",
    "Under-prepared": "#f97316", "Critical": "#ef4444",
  };
  const color = readinessColors[profile.readiness_level] || "#888";
  const pct = (profile.readiness_score * 100).toFixed(0);

  let html = `
    <!-- Header -->
    <div style="text-align:center;margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid var(--border)">
      <div style="font-size:1.3rem;font-weight:800;color:var(--text-bright)">${profile.facility_name}</div>
      <div style="font-size:0.78rem;color:var(--text-dim);margin-top:0.25rem">${profile.facility_id} · ${profile.facility_type} · ${profile.district}</div>
      <div style="font-size:0.72rem;color:var(--text-dim);margin-top:0.15rem">${profile.region}</div>
    </div>

    <!-- Readiness Score -->
    <div style="text-align:center;margin-bottom:1.5rem">
      <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim)">READINESS SCORE</div>
      <div style="font-size:2.5rem;font-weight:800;color:${color}">${pct}%</div>
      <div class="risk-badge risk-badge--${profile.readiness_level === 'Ready' ? 'low' : profile.readiness_level === 'Partially Ready' ? 'moderate' : 'high'}" style="font-size:0.85rem;padding:0.4rem 1.2rem">${profile.readiness_level}</div>
      <div class="progress-bar" style="margin-top:0.75rem"><div class="progress-bar__fill" style="width:${pct}%;background:linear-gradient(90deg,var(--danger),var(--warning),var(--success))"></div></div>
    </div>

    <!-- Readiness Indicators -->
    <div class="section-heading" style="margin-bottom:0.75rem"><i data-lucide="clipboard-list"></i> Available Readiness Indicators</div>
    <div class="grid-4 mb-1">
      <div class="metric">
        <div class="metric__label">Beds Available</div>
        <div class="metric__value">${profile.beds_available}</div>
      </div>
      <div class="metric">
        <div class="metric__label">Health Workers</div>
        <div class="metric__value">${profile.health_workers}</div>
      </div>
      <div class="metric">
        <div class="metric__label">Medicine Stock</div>
        <div class="metric__value" style="color:${profile.malaria_medicine_stock < 0.3 ? 'var(--danger)' : 'var(--text-bright)'}">${(profile.malaria_medicine_stock * 100).toFixed(0)}%</div>
      </div>
      <div class="metric">
        <div class="metric__label">Patient Load</div>
        <div class="metric__value">${profile.patient_load}</div>
      </div>
    </div>

    <div class="grid-3 mb-1">
      <div class="metric">
        <div class="metric__label">Power Supply</div>
        <div class="metric__value" style="color:${profile.power_availability ? '#22c55e' : '#ef4444'}">${profile.power_availability ? '✓ Available' : '✗ Unavailable'}</div>
      </div>
      <div class="metric">
        <div class="metric__label">Water Supply</div>
        <div class="metric__value" style="color:${profile.water_availability ? '#22c55e' : '#ef4444'}">${profile.water_availability ? '✓ Available' : '✗ Unavailable'}</div>
      </div>
      <div class="metric">
        <div class="metric__label">Staff:Patient Ratio</div>
        <div class="metric__value">${profile.staff_ratio ?? 'N/A'}</div>
      </div>
    </div>

    <!-- Key Gaps -->
    <div class="section-heading" style="margin-bottom:0.5rem"><i data-lucide="alert-triangle"></i> Key Gaps</div>
    <ul class="result-list result-list--${profile.key_gaps[0] === 'No critical gaps identified' ? 'success' : 'danger'}" style="margin-bottom:1.25rem">
      ${profile.key_gaps.map(g => `<li>${g}</li>`).join("")}
    </ul>
  `;

  // Risk Exposure
  if (earlyWarning && earlyWarning.hazard_exposure) {
    html += `<div class="section-heading" style="margin-bottom:0.5rem"><i data-lucide="cloud-lightning"></i> Risk Exposure</div>`;
    html += `<div class="grid-${Math.min(earlyWarning.hazard_exposure.length, 3)}" style="margin-bottom:1rem">`;
    earlyWarning.hazard_exposure.forEach(h => {
      const hColor = h.risk_level === 'High' ? 'var(--danger)' : h.risk_level === 'Moderate' ? 'var(--warning)' : 'var(--success)';
      html += `
        <div class="result-panel" style="border-left:3px solid ${hColor};padding:0.75rem">
          <div style="font-weight:700;font-size:0.82rem;color:var(--text-bright)">${h.hazard}</div>
          <div style="font-size:0.78rem;color:${hColor};font-weight:600">${h.risk_level}</div>
          <div style="font-size:0.68rem;color:var(--text-dim);margin-top:0.25rem">${h.detail}</div>
          <div style="font-size:0.62rem;color:var(--text-dim);font-style:italic;margin-top:0.15rem">Source: ${h.data_source}</div>
        </div>
      `;
    });
    html += `</div>`;
  }

  // Preparedness Recommendations
  if (earlyWarning && earlyWarning.preparedness_recommendations) {
    html += `<div class="section-heading" style="margin-bottom:0.5rem"><i data-lucide="check-circle"></i> Preparedness Recommendations</div>`;
    html += `<ul class="result-list result-list--success" style="margin-bottom:1rem">`;
    earlyWarning.preparedness_recommendations.forEach(r => { html += `<li>${r}</li>`; });
    html += `</ul>`;
  }

  // Unavailable Data
  html += `
    <div class="section-heading" style="margin-bottom:0.5rem"><i data-lucide="help-circle"></i> Unavailable Data</div>
    <div class="result-panel result-panel--info" style="margin-bottom:1rem">
      <div style="font-size:0.75rem;color:var(--text-dim);line-height:1.6">
        <div><strong>Services offered:</strong> ${profile.services_offered}</div>
        <div><strong>Operational status:</strong> ${profile.operational_status}</div>
        <div><strong>Ownership:</strong> ${profile.ownership}</div>
        <div><strong>Emergency plan:</strong> ${profile.emergency_plan}</div>
        <div><strong>Road access:</strong> ${profile.road_access}</div>
        <div><strong>Building condition:</strong> ${profile.building_condition}</div>
        <div><strong>Population served:</strong> ${profile.population_served}</div>
      </div>
    </div>
  `;

  // Coordinate note
  if (profile.coord_source === 'approximate_district_centroid') {
    html += `
      <div class="result-panel result-panel--info" style="font-size:0.72rem;padding:0.6rem">
        <strong>⚠ Location note:</strong> Coordinates are approximate (district centroid). Real DHIS2 coordinates are not yet integrated.
      </div>
    `;
  }

  // Early warning note
  if (earlyWarning?.note) {
    html += `<div style="font-size:0.65rem;color:var(--text-dim);margin-top:0.75rem;font-style:italic">${earlyWarning.note}</div>`;
  }

  content.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// --- Data Quality Report ---
function renderDataQuality(quality) {
  const el = document.getElementById("mfl-data-quality");
  if (!el) return;

  const gradeColors = { Excellent: "#22c55e", Good: "#22c55e", Fair: "#f59e0b", Poor: "#ef4444" };
  const gradeColor = gradeColors[quality.quality_grade] || "#888";

  let html = `
    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem">
      <div style="font-size:2rem;font-weight:800;color:${gradeColor}">${quality.quality_grade}</div>
      <div style="font-size:0.78rem;color:var(--text-dim)">${quality.total_facilities} facilities · ${quality.total_issues} issues identified</div>
    </div>
  `;

  if (quality.issues && quality.issues.length) {
    html += `<div style="display:flex;flex-direction:column;gap:0.5rem;margin-bottom:1rem">`;
    quality.issues.forEach(issue => {
      const sevColors = { error: "#ef4444", warning: "#f59e0b", info: "#6366f1" };
      const sevColor = sevColors[issue.severity] || "#888";
      html += `
        <div style="display:flex;align-items:flex-start;gap:0.75rem;padding:0.6rem;background:var(--card-bg);border-radius:var(--radius-sm);border-left:3px solid ${sevColor}">
          <div style="min-width:60px;font-size:0.68rem;font-weight:700;text-transform:uppercase;color:${sevColor}">${issue.severity}</div>
          <div>
            <div style="font-weight:600;font-size:0.78rem;color:var(--text-bright)">${issue.check} <span style="font-weight:400;color:var(--text-dim)">(${issue.count})</span></div>
            <div style="font-size:0.72rem;color:var(--text-dim);margin-top:0.15rem">${issue.description}</div>
          </div>
        </div>
      `;
    });
    html += `</div>`;
  }

  if (quality.unavailable_fields && quality.unavailable_fields.length) {
    html += `<div class="section-heading" style="margin-bottom:0.5rem"><i data-lucide="info"></i> Fields Not Yet Available</div>`;
    html += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.35rem;font-size:0.72rem">`;
    quality.unavailable_fields.forEach(f => {
      html += `
        <div style="padding:0.4rem 0.6rem;background:var(--card-bg);border-radius:var(--radius-sm)">
          <div style="font-weight:600;color:var(--text)">${f.field}</div>
          <div style="color:var(--text-dim);font-size:0.68rem">${f.source_needed}</div>
        </div>
      `;
    });
    html += `</div>`;
  }

  el.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// --- Initialize on page load ---
document.addEventListener("DOMContentLoaded", () => {
  loadMflData();
});

// --- Hash Routing ---
(function initFromHash() {
  const h = location.hash.slice(1);
  if (h && ["facilities", "forecast", "anomaly", "surge", "ml-predictions"].includes(h)) switchTab(h);
})();

window.addEventListener('hashchange', () => {
  const tabId = window.location.hash.substring(1);
  if (tabId && typeof switchTab === 'function') switchTab(tabId);
});
