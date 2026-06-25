/**
 * CHEWS v3.0 — Healthcare Readiness Logic
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
        <div class="progress-bar"><div class="progress-bar__fill" style="width:${data.onset_likelihood*100}%;background:var(--accent-2)"></div></div>
      </div>
      <div class="metric">
        <div class="metric__icon"><i data-lucide="bar-chart-2"></i></div>
        <div class="metric__label">Surge Probability</div>
        <div class="metric__value" style="font-size:1.3rem;color:${data.surge_probability > 0.6 ? 'var(--danger)' : 'var(--warning)'}">${(data.surge_probability * 100).toFixed(0)}%</div>
        <div class="progress-bar"><div class="progress-bar__fill" style="width:${data.surge_probability*100}%;background:linear-gradient(90deg,var(--warning),var(--danger))"></div></div>
      </div>
      <div class="metric">
        <div class="metric__icon"><i data-lucide="calendar"></i></div>
        <div class="metric__label">Peak Window</div>
        <div class="metric__value" style="font-size:1rem">${data.peak_window}</div>
        <div class="metric__trend">Confidence: ${(data.confidence*100).toFixed(0)}%</div>
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
    <div class="progress-bar mb-1"><div class="progress-bar__fill" style="width:${data.readiness_score*100}%;background:linear-gradient(90deg,var(--danger),var(--warning),var(--success))"></div></div>

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
      sorted.map(([k, v]) => `<div class="contrib"><span class="contrib__lbl">${k.replace(/_/g, " ")}</span><div class="contrib__track"><div class="contrib__fill" style="width:${(v*100).toFixed(0)}%;background:var(--accent-2)"></div></div><span class="contrib__val">${(v*100).toFixed(0)}%</span></div>`).join("") +
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
      sorted.map(([k, v]) => `<div class="contrib"><span class="contrib__lbl">${k.replace(/_/g, " ")}</span><div class="contrib__track"><div class="contrib__fill" style="width:${(v*100).toFixed(0)}%;background:var(--success)"></div></div><span class="contrib__val">${(v*100).toFixed(0)}%</span></div>`).join("") +
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
      sorted.map(([k, v]) => `<div class="contrib"><span class="contrib__lbl">${k.replace(/_/g, " ")}</span><div class="contrib__track"><div class="contrib__fill" style="width:${(v*100).toFixed(0)}%;background:var(--warning)"></div></div><span class="contrib__val">${(v*100).toFixed(0)}%</span></div>`).join("") +
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

(function initFromHash() {
  const h = location.hash.slice(1);
  if (h && ["forecast", "anomaly", "surge", "ml-predictions"].includes(h)) switchTab(h);
})();

// Tab Hash Routing
window.addEventListener('DOMContentLoaded', () => {
  if (window.location.hash) {
    const tabId = window.location.hash.substring(1);
    if (typeof switchTab === 'function') switchTab(tabId);
  }
});

window.addEventListener('hashchange', () => {
  const tabId = window.location.hash.substring(1);
  if (tabId && typeof switchTab === 'function') switchTab(tabId);
});
