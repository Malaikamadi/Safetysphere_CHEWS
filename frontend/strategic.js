/**
 * CHEWS v3.0 — Strategic Planning Logic
 */
const API = "http://127.0.0.1:8000";

// Mobile menu
const mt = document.getElementById("menu-toggle"), sb = document.getElementById("sidebar");
if (mt && sb) { mt.addEventListener("click", () => sb.classList.toggle("sidebar--open")); }

// Tab switching
function switchTab(tab) {
  document.querySelectorAll(".tab-content").forEach(t => t.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(b => { b.classList.remove("active-tab"); b.classList.add("btn--ghost"); b.classList.remove("btn--secondary"); });
  document.getElementById("tab-" + tab).classList.remove("hidden");
  const activeBtn = document.querySelector(`[data-tab="${tab}"]`);
  activeBtn.classList.add("active-tab", "btn--secondary");
  activeBtn.classList.remove("btn--ghost");
}

function renderResult(containerId, data, title) {
  const el = document.getElementById(containerId);
  el.classList.remove("hidden");
  el.classList.add("slide-up");
  let html = "";

  if (data.composite_score !== undefined) {
    const lvlClass = data.vulnerability_level.toLowerCase().replace(/\s+/g, '-');
    html += `<div style="text-align:center;margin-bottom:1rem"><div class="risk-badge risk-badge--${lvlClass}">${data.vulnerability_level} — ${data.priority_rank}</div></div>`;
    html += `<div class="grid-3 mb-1">
      <div class="metric"><div class="metric__label">Hazard Exposure</div><div class="metric__value text-danger">${data.hazard_exposure.toFixed(2)}</div></div>
      <div class="metric"><div class="metric__label">Pop. Sensitivity</div><div class="metric__value text-warning">${data.population_sensitivity.toFixed(2)}</div></div>
      <div class="metric"><div class="metric__label">Adaptive Capacity</div><div class="metric__value text-accent">${data.adaptive_capacity.toFixed(2)}</div></div>
    </div>`;
    html += `<div style="text-align:center;font-size:2rem;font-weight:800;color:var(--text-bright);margin-bottom:0.5rem">${data.composite_score.toFixed(2)}</div>`;
    html += `<div class="progress-bar mb-1"><div class="progress-bar__fill" style="width:${data.composite_score*100}%;background:linear-gradient(90deg,var(--success),var(--warning),var(--danger))"></div></div>`;
  }

  if (data.hazard_layers) {
    html += `<div class="grid-4 mb-1">`;
    for (const [key, val] of Object.entries(data.hazard_layers)) {
      const score = val.score || val.health_risk || 0;
      html += `<div class="metric"><div class="metric__label">${key}</div><div class="metric__value">${val.aqi || score.toFixed(2)}</div><div class="metric__trend">${val.category || val.level || ''}</div></div>`;
    }
    html += `</div>`;
    html += `<div style="text-align:center;margin-bottom:1rem"><span class="risk-badge risk-badge--${data.composite_hazard > 0.6 ? 'high' : data.composite_hazard > 0.3 ? 'moderate' : 'low'}">Composite: ${data.composite_hazard.toFixed(2)}</span></div>`;
  }

  if (data.aqi !== undefined) {
    html += `<div style="text-align:center;margin-bottom:1rem">
      <div style="font-size:3rem;font-weight:800;color:var(--text-bright)">${data.aqi}</div>
      <div class="risk-badge risk-badge--${data.is_hotspot ? 'high' : 'low'}">${data.category}${data.is_hotspot ? ' — HOTSPOT' : ''}</div>
    </div>`;
    if (data.pollutant_scores) {
      html += `<div class="grid-3 mb-1">`;
      for (const [k, v] of Object.entries(data.pollutant_scores)) { html += `<div class="metric"><div class="metric__label">${k}</div><div class="metric__value">${v}</div></div>`; }
      html += `</div>`;
    }
    html += `<div class="metric mb-1"><div class="metric__label">Dominant Pollutant</div><div class="metric__value">${data.dominant_pollutant}</div></div>`;
  }

  if (data.total_co2e_kg !== undefined) {
    html += `<div style="text-align:center;margin-bottom:1rem"><div style="font-size:2.5rem;font-weight:800;color:var(--text-bright)">${data.total_co2e_kg.toFixed(1)} <span style="font-size:1rem;color:var(--text-dim)">kg CO₂e/month</span></div></div>`;
    html += `<div class="grid-3 mb-1">
      <div class="metric"><div class="metric__label">Scope 1 (Direct)</div><div class="metric__value">${data.scope1_kg.toFixed(1)}</div></div>
      <div class="metric"><div class="metric__label">Scope 2 (Electricity)</div><div class="metric__value">${data.scope2_kg.toFixed(1)}</div></div>
      <div class="metric"><div class="metric__label">Scope 3 (Supply)</div><div class="metric__value">${data.scope3_kg.toFixed(1)}</div></div>
    </div>`;
    html += `<div class="result-panel result-panel--info mb-1"><div class="section-heading">Benchmark</div><p style="font-size:0.82rem">${data.benchmark_comparison} · Intensity: ${data.intensity_per_sqm.toFixed(2)} kg/m² · Reduction potential: ${data.reduction_potential_pct}%</p></div>`;
  }

  if (data.factors && data.factors.length) {
    html += `<div class="mb-1"><div class="section-heading"><i data-lucide="zap"></i> Key Factors</div><ul class="result-list result-list--warning">`;
    data.factors.forEach(f => html += `<li>${f}</li>`);
    html += `</ul></div>`;
  }
  if (data.recommendations && data.recommendations.length) {
    html += `<div class="mb-1"><div class="section-heading"><i data-lucide="check-circle"></i> Recommendations</div><ul class="result-list result-list--success">`;
    data.recommendations.forEach(r => html += `<li>${r}</li>`);
    html += `</ul></div>`;
  }
  el.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

async function postForm(url, payload, resultId) {
  try {
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    renderResult(resultId, await res.json());
  } catch (e) { alert("Error: " + e.message + "\n\nEnsure backend is running on port 8000."); }
}

// Vulnerability
document.getElementById("vuln-form").addEventListener("submit", e => {
  e.preventDefault();
  postForm(`${API}/strategic/vulnerability-score`, {
    facility_type: document.getElementById("v-facility-type").value,
    building_type: document.getElementById("v-building-type").value,
    staff_count: +document.getElementById("v-staff").value,
    water_source: document.getElementById("v-water").value,
    power_source: document.getElementById("v-power").value,
    road_access: document.getElementById("v-road").value,
    population_under5: +document.getElementById("v-under5").value,
    population_pregnant: +document.getElementById("v-pregnant").value,
    total_population: +document.getElementById("v-total").value,
    flood_risk: +document.getElementById("v-flood").value,
    heat_risk: +document.getElementById("v-heat").value,
    air_quality_risk: +document.getElementById("v-aq").value,
    has_emergency_plan: document.getElementById("v-plan").checked,
  }, "vuln-result");
});

// Hazard Map
document.getElementById("hazard-form").addEventListener("submit", e => {
  e.preventDefault();
  postForm(`${API}/strategic/hazard-map`, {
    location_name: document.getElementById("h-name").value,
    latitude: +document.getElementById("h-lat").value,
    longitude: +document.getElementById("h-lng").value,
    rainfall: +document.getElementById("h-rain").value,
    temperature: +document.getElementById("h-temp").value,
    humidity: +document.getElementById("h-hum").value,
    pm25: +document.getElementById("h-pm25").value,
    rainfall_intensity: +document.getElementById("h-intensity").value,
    elevation: +document.getElementById("h-elev").value,
  }, "hazard-result");
});

// Pollution
document.getElementById("pollution-form").addEventListener("submit", e => {
  e.preventDefault();
  postForm(`${API}/strategic/pollution-hotspot`, {
    pm25: +document.getElementById("p-pm25").value,
    pm10: +document.getElementById("p-pm10").value,
    o3: +document.getElementById("p-o3").value,
    no2: +document.getElementById("p-no2").value,
    so2: +document.getElementById("p-so2").value,
    has_children: document.getElementById("p-children").checked,
    has_respiratory_conditions: document.getElementById("p-resp").checked,
  }, "pollution-result");
});

// Carbon
document.getElementById("carbon-form").addEventListener("submit", e => {
  e.preventDefault();
  postForm(`${API}/strategic/carbon-footprint`, {
    facility_type: document.getElementById("c-type").value,
    floor_area_sqm: +document.getElementById("c-area").value,
    diesel_liters_month: +document.getElementById("c-diesel").value,
    charcoal_kg_month: +document.getElementById("c-charcoal").value,
    kerosene_liters_month: +document.getElementById("c-kerosene").value,
    electricity_kwh_month: +document.getElementById("c-elec").value,
    generator_hours_month: +document.getElementById("c-gen").value,
    solar_kwh_month: +document.getElementById("c-solar").value,
    has_solar: document.getElementById("c-has-solar").checked,
  }, "carbon-result");
});

document.querySelectorAll("a.nav-link--soon").forEach((a) => a.addEventListener("click", (e) => e.preventDefault()));

(function initFromHash() {
  const h = location.hash.slice(1);
  if (h && ["vulnerability", "hazard", "pollution", "carbon"].includes(h)) switchTab(h);
})();
