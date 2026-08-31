/**
 * CHEWS v3.0 — Healthcare Readiness Logic
 */
const API = "/api";

const mt = document.getElementById("menu-toggle"), sb = document.getElementById("sidebar");
if (mt && sb) { mt.addEventListener("click", () => sb.classList.toggle("sidebar--open")); }

function switchTab(tab) {
  const panel = document.getElementById("tab-" + tab);
  if (!panel) return;
  document.querySelectorAll(".tab-content").forEach(t => t.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(b => { b.classList.remove("active-tab", "btn--secondary"); b.classList.add("btn--ghost"); });
  panel.classList.remove("hidden");
  const btn = document.querySelector(`[data-tab="${tab}"]`);
  if (btn) { btn.classList.add("active-tab", "btn--secondary"); btn.classList.remove("btn--ghost"); }
}

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

function bindChips() {
  document.querySelectorAll(".hc-chip[data-target]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const targetId = chip.getAttribute("data-target");
      const hidden = document.getElementById(targetId);
      if (hidden) hidden.value = chip.getAttribute("data-value");
      chip.parentElement.querySelectorAll(".hc-chip").forEach((c) => c.classList.remove("is-on"));
      chip.classList.add("is-on");
      if (targetId === "f-disease") {
        const wrap = document.getElementById("f-aqi-wrap");
        if (wrap) wrap.hidden = chip.getAttribute("data-value") !== "respiratory";
        runForecast();
      }
      if (targetId === "s-disease") runSurge();
    });
  });
}
bindChips();

function riskClass(level) {
  const k = (level || "").toLowerCase().replace(/\s+/g, "-");
  if (k === "very-high" || k === "critical" || k === "critical-gap") return "high";
  if (k === "at-risk") return "high";
  if (k === "partially-ready") return "moderate";
  if (k === "ready") return "low";
  return k;
}

function listItems(arr) {
  return (arr || []).map((t) => `<li>${t}</li>`).join("");
}

function showResultError(el, msg) {
  if (!el) return;
  el.innerHTML = `<p class="hc-result__error">${msg}</p>`;
}

async function runForecast() {
  const el = document.getElementById("forecast-result");
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
    if (!res.ok) throw new Error(`Could not load outlook (${res.status})`);
    renderForecast(await res.json());
  } catch (err) {
    showResultError(el, err.message);
  }
}

document.getElementById("forecast-form")?.addEventListener("submit", (e) => {
  e.preventDefault();
  runForecast();
});

function renderForecast(data) {
  const el = document.getElementById("forecast-result");
  if (!el) return;
  const month = MONTHS[(+document.getElementById("f-month").value || 1) - 1];
  const lvl = data.predicted_risk_level;
  const trendColor = { Rising: "var(--danger)", Stable: "var(--text-dim)", Declining: "var(--success)" }[data.risk_trend];
  const surgeColor = data.surge_probability > 0.6 ? "var(--danger)" : data.surge_probability > 0.4 ? "var(--warning)" : "var(--success)";

  el.innerHTML = `
    <div class="hc-hero">
      <div class="hc-hero__kicker">${data.disease} · next 4 weeks from ${month}</div>
      <div class="hc-hero__row">
        <div class="hc-hero__level risk-badge risk-badge--${riskClass(lvl)}">${lvl} load</div>
        <p class="hc-hero__note">Peak season typically ${data.peak_window}. Confidence ${(data.confidence * 100).toFixed(0)}%.</p>
      </div>
    </div>
    <div class="hc-stat-grid">
      <div class="hc-stat">
        <div class="hc-stat__label">Trend</div>
        <div class="hc-stat__value" style="color:${trendColor}">${data.risk_trend}</div>
        <div class="hc-stat__sub">from recent case counts</div>
      </div>
      <div class="hc-stat">
        <div class="hc-stat__label">Chance of onset</div>
        <div class="hc-stat__value">${(data.onset_likelihood * 100).toFixed(0)}%</div>
        <div class="hc-meter"><span style="width:${data.onset_likelihood * 100}%"></span></div>
      </div>
      <div class="hc-stat">
        <div class="hc-stat__label">Chance of surge</div>
        <div class="hc-stat__value" style="color:${surgeColor}">${(data.surge_probability * 100).toFixed(0)}%</div>
        <div class="hc-meter"><span style="width:${data.surge_probability * 100}%;background:${surgeColor}"></span></div>
      </div>
      <div class="hc-stat">
        <div class="hc-stat__label">Peak window</div>
        <div class="hc-stat__value hc-stat__value--sm">${data.peak_window}</div>
        <div class="hc-stat__sub">usual high-transmission months</div>
      </div>
    </div>
    <div class="hc-split">
      <div class="hc-panel">
        <h3 class="hc-panel__title">What’s driving this</h3>
        <ul class="hc-list">${listItems(data.factors)}</ul>
      </div>
      <div class="hc-panel">
        <h3 class="hc-panel__title">What to do</h3>
        <ul class="hc-list hc-list--do">${listItems(data.recommendations)}</ul>
      </div>
    </div>
  `;
}

// === Surge Planning ===
async function runSurge() {
  const el = document.getElementById("surge-result");
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
    if (!res.ok) throw new Error(`Could not load plan (${res.status})`);
    renderSurge(await res.json());
  } catch (err) {
    showResultError(el, err.message);
  }
}

document.getElementById("surge-form")?.addEventListener("submit", (e) => {
  e.preventDefault();
  runSurge();
});

function renderSurge(data) {
  const el = document.getElementById("surge-result");
  if (!el) return;
  const beds = +document.getElementById("s-beds").value;
  const staff = +document.getElementById("s-staff").value;
  const expected = data.expected_surge_cases;
  const bedGap = Math.max(0, expected - beds);
  const bedSpare = Math.max(0, beds - expected);
  const bedsShort = bedGap > 0;
  const staffNeeded = Math.max(0, Math.ceil(expected * 0.3) - staff);
  const staffShort = staffNeeded > 0 || data.staff_patient_ratio < 0.3;
  const supplyShort = data.supply_days_remaining < 14;
  const patientsPerStaff = data.staff_patient_ratio > 0 ? Math.round(1 / data.staff_patient_ratio) : "—";
  const lvl = data.readiness_level;
  const lvlColor = { Ready: "var(--success)", "Partially Ready": "var(--warning)", "At Risk": "var(--orange)", "Critical Gap": "var(--danger)" }[lvl] || "var(--text)";

  el.innerHTML = `
    <div class="hc-hero">
      <div class="hc-hero__kicker">${data.disease} · ${data.current_cases} cases now → ${expected} expected</div>
      <div class="hc-hero__row">
        <div class="hc-hero__level risk-badge risk-badge--${riskClass(lvl)}">${lvl}</div>
        <p class="hc-hero__note">Readiness <strong style="color:${lvlColor}">${(data.readiness_score * 100).toFixed(0)}%</strong> against the extra load.</p>
      </div>
    </div>
    <div class="hc-need-grid">
      <div class="hc-need ${bedsShort ? "hc-need--short" : "hc-need--ok"}">
        <div class="hc-need__label">Beds</div>
        <div class="hc-need__value">${bedsShort ? bedGap + " short" : bedSpare + " spare"}</div>
        <div class="hc-need__sub">${expected} expected · ${beds} available · ${data.bed_utilization_pct}% used</div>
      </div>
      <div class="hc-need ${staffShort ? "hc-need--short" : "hc-need--ok"}">
        <div class="hc-need__label">Staff</div>
        <div class="hc-need__value">${staffShort ? (staffNeeded ? staffNeeded + " more" : "thin coverage") : "enough"}</div>
        <div class="hc-need__sub">${staff} on duty · about 1 staff per ${patientsPerStaff} patients</div>
      </div>
      <div class="hc-need ${supplyShort ? "hc-need--short" : "hc-need--ok"}">
        <div class="hc-need__label">Supplies</div>
        <div class="hc-need__value">${data.supply_days_remaining} days</div>
        <div class="hc-need__sub">${supplyShort ? "Below the 14-day buffer — reorder now" : "At or above the 14-day buffer"}</div>
      </div>
    </div>
    <div class="hc-split">
      <div class="hc-panel">
        <h3 class="hc-panel__title">Gaps</h3>
        <ul class="hc-list">${listItems(data.gaps)}</ul>
      </div>
      <div class="hc-panel">
        <h3 class="hc-panel__title">What to do</h3>
        <ul class="hc-list hc-list--do">${listItems(data.recommendations)}</ul>
      </div>
    </div>
  `;
}

document.querySelectorAll("a.nav-link--soon").forEach((a) => a.addEventListener("click", (e) => e.preventDefault()));

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
  if (window.chewsTheme && window.chewsTheme.attachBasemap) {
    window.chewsTheme.attachBasemap(mflMap);
  } else {
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; OSM &copy; CARTO',
      maxZoom: 18,
    }).addTo(mflMap);
  }

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
  runForecast();
  runSurge();
});

// --- Hash Routing ---
(function initFromHash() {
  const h = location.hash.slice(1);
  if (h && ["facilities", "forecast", "surge"].includes(h)) switchTab(h);
})();

window.addEventListener('hashchange', () => {
  const tabId = window.location.hash.substring(1);
  if (tabId && ["facilities", "forecast", "surge"].includes(tabId) && typeof switchTab === 'function') switchTab(tabId);
});
