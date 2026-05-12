/**
 * CHEWS v3.0 — Early Warning Logic
 */
const API = "http://127.0.0.1:8000";

// Mobile menu
const mt = document.getElementById("menu-toggle"), sb = document.getElementById("sidebar");
if (mt && sb) { mt.addEventListener("click", () => sb.classList.toggle("sidebar--open")); }

const SEVERITY_ICONS = { Emergency: `<i data-lucide="alert-circle" class="text-danger"></i>`, Warning: `<i data-lucide="alert-triangle" class="text-warning"></i>`, Watch: `<i data-lucide="info" class="text-warning"></i>`, Advisory: `<i data-lucide="info" class="text-accent-2"></i>`, Info: `<i data-lucide="info"></i>` };
const SEVERITY_CLASS = { Emergency: "emergency", Warning: "warning", Watch: "watch", Advisory: "advisory" };

// Comprehensive Assessment
document.getElementById("ew-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    location: document.getElementById("ew-loc").value,
    temperature: +document.getElementById("ew-temp").value,
    humidity: +document.getElementById("ew-hum").value,
    rainfall_intensity: +document.getElementById("ew-rain-i").value,
    rainfall_24h: +document.getElementById("ew-rain-24").value,
    elevation: +document.getElementById("ew-elev").value,
    pm25: +document.getElementById("ew-pm25").value,
    pm10: +document.getElementById("ew-pm10").value,
    uv_index: +document.getElementById("ew-uv").value,
    soil_saturation: 60,
  };

  try {
    const res = await fetch(`${API}/early-warning/assess`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data = await res.json();
    renderAssessment(data);
    loadAlerts();
  } catch (err) {
    alert("Error: " + err.message + "\n\nEnsure backend is running on port 8000.");
  }
});

function renderAssessment(data) {
  const el = document.getElementById("ew-result");
  el.classList.remove("hidden");
  el.classList.add("slide-up");

  const threatColors = { Normal: "var(--success)", Guarded: "var(--accent-2)", Elevated: "var(--warning)", High: "var(--orange)", Critical: "var(--danger)" };
  const threatColor = threatColors[data.overall_threat_level] || "var(--text)";

  let html = `
    <div style="text-align:center;margin-bottom:1.25rem">
      <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim);margin-bottom:0.35rem">Overall Threat Level</div>
      <div style="font-size:2rem;font-weight:800;color:${threatColor}">${data.overall_threat_level}</div>
      <div style="font-size:0.72rem;color:var(--text-dim)">${data.location} · ${new Date(data.assessment_time).toLocaleString()}</div>
    </div>
    <div class="grid-4 mb-1">`;

  // Hazard cards
  const hazardConfig = {
    air_quality: { icon: `<i data-lucide="wind"></i>`, label: "Air Quality", main: `AQI ${data.hazards.air_quality.aqi}`, sub: data.hazards.air_quality.category },
    flood: { icon: `<i data-lucide="waves"></i>`, label: "Flood Risk", main: data.hazards.flood.score.toFixed(2), sub: data.hazards.flood.level },
    heat: { icon: `<i data-lucide="thermometer"></i>`, label: "Heat Stress", main: `${data.hazards.heat.wbgt}°C`, sub: data.hazards.heat.category },
    uv: { icon: `<i data-lucide="sun"></i>`, label: "UV Index", main: data.hazards.uv.index.toFixed(1), sub: data.hazards.uv.level },
  };

  for (const [, cfg] of Object.entries(hazardConfig)) {
    html += `<div class="metric"><div class="metric__icon">${cfg.icon}</div><div class="metric__label">${cfg.label}</div><div class="metric__value">${cfg.main}</div><div class="metric__trend">${cfg.sub}</div></div>`;
  }
  html += `</div>`;

  // Active alerts from this assessment
  if (data.active_alerts && data.active_alerts.length) {
    html += `<div class="section-heading"><i data-lucide="alert-triangle"></i> Alerts Triggered</div><div class="alert-feed mb-1">`;
    data.active_alerts.forEach(a => {
      html += renderAlertItem(a);
    });
    html += `</div>`;
  }

  // UV actions
  if (data.hazards.uv.actions && data.hazards.uv.actions.length) {
    html += `<div class="section-heading"><i data-lucide="sun"></i> UV Protection</div><ul class="result-list result-list--warning mb-1">`;
    data.hazards.uv.actions.forEach(a => html += `<li>${a}</li>`);
    html += `</ul>`;
  }

  // Flood impact
  if (data.hazards.flood.impact) {
    html += `<div class="result-panel result-panel--info"><div class="section-heading"><i data-lucide="waves"></i> Flood Impact</div><p style="font-size:0.82rem">${data.hazards.flood.impact}</p></div>`;
  }

  el.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

function renderAlertItem(a) {
  const icon = SEVERITY_ICONS[a.severity] || `<i data-lucide="info"></i>`;
  const cls = SEVERITY_CLASS[a.severity] || "advisory";
  return `<div class="alert-item">
    <div class="alert-item__severity alert-item__severity--${cls}">${icon}</div>
    <div class="alert-item__body">
      <div class="alert-item__title">${a.title}</div>
      <div class="alert-item__desc">${a.description}</div>
      <div class="alert-item__time">${a.affected_area} · ${a.auto_trigger ? '<i data-lucide="zap"></i> Auto-trigger' : 'Manual'}</div>
    </div>
  </div>`;
}

// Manual Trigger
document.getElementById("trigger-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await fetch(`${API}/early-warning/trigger`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hazard_type: document.getElementById("tr-type").value,
        current_value: +document.getElementById("tr-value").value,
        location: document.getElementById("tr-loc").value,
      }),
    });
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data = await res.json();
    const el = document.getElementById("trigger-result");
    el.classList.remove("hidden");
    el.classList.add("slide-up");
    if (data.triggered) {
      el.innerHTML = `<div class="result-panel result-panel--danger">${renderAlertItem(data.alert)}</div>`;
    } else {
      el.innerHTML = `<div class="result-panel result-panel--accent"><p style="font-size:0.85rem;color:var(--success)"><i data-lucide="check-circle"></i> ${data.message}</p></div>`;
    }
    loadAlerts();
  } catch (err) {
    alert("Error: " + err.message);
  }
});

// Load alerts
async function loadAlerts() {
  try {
    const res = await fetch(`${API}/early-warning/alerts?min_severity=Advisory`);
    if (!res.ok) return;
    const data = await res.json();
    const feed = document.getElementById("alert-feed-ew");
    if (!data.alerts || !data.alerts.length) {
      feed.innerHTML = `<div style="text-align:center;padding:1.5rem 0;color:var(--text-dim);font-size:0.82rem">No active alerts</div>`;
      return;
    }
    feed.innerHTML = data.alerts.map(a => renderAlertItem(a)).join("");
    if (window.lucide) lucide.createIcons();
  } catch { /* ignore */ }
}

loadAlerts();

document.querySelectorAll("a.nav-link--soon").forEach((a) => a.addEventListener("click", (e) => e.preventDefault()));
