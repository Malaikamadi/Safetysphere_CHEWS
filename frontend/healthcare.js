/**
 * CHEWS — Healthcare Readiness
 * Live dashboard: models run on ingested feeds. Users view, they do not calculate.
 */
const API = "/api";
const LIVE_REFRESH_MS = 60_000;

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
  if (tab === "facilities" && mflMap) {
    setTimeout(() => mflMap.invalidateSize(), 80);
  }
}

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DISEASE_LABEL = {
  malaria: "Malaria",
  cholera: "Cholera",
  dengue: "Dengue",
  respiratory: "Acute respiratory infection",
};
const STAFF_PER_PATIENT = 1 / 3; // target: 1 clinician per 3 patients
const SUPPLY_BUFFER_DAYS = 14;

function diseaseLabel(id) {
  return DISEASE_LABEL[id] || (id ? id.charAt(0).toUpperCase() + id.slice(1) : "—");
}

function adminLabel(selId) {
  const el = document.getElementById(selId);
  if (!el) return "National";
  const opt = el.options[el.selectedIndex];
  return opt ? opt.text : "National";
}

function riskClass(level) {
  const k = (level || "").toLowerCase().replace(/\s+/g, "-");
  if (k === "very-high" || k === "critical" || k === "critical-gap") return "critical";
  if (k === "at-risk" || k === "high") return "high";
  if (k === "partially-ready" || k === "moderate") return "moderate";
  if (k === "ready" || k === "low") return "low";
  return "moderate";
}

function showResultError(el, msg) {
  if (!el) return;
  el.innerHTML = `<p class="his-output__error">${msg}</p>`;
}

function liveQuery(diseaseId, adminId) {
  const disease = document.getElementById(diseaseId)?.value || "malaria";
  const admin = document.getElementById(adminId)?.value || "national";
  return `disease=${encodeURIComponent(disease)}&admin=${encodeURIComponent(admin)}`;
}

function setLiveStamp(id, iso) {
  const el = document.getElementById(id);
  if (!el) return;
  const t = iso ? new Date(iso) : new Date();
  const label = Number.isNaN(t.getTime())
    ? "Live"
    : `Live · ${t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  el.innerHTML = `<span class="pulse-dot"></span> ${label}`;
}

async function loadLiveForecast() {
  const el = document.getElementById("forecast-result");
  try {
    const res = await fetch(`${API}/healthcare/forecast/live?${liveQuery("f-disease", "f-admin")}`);
    if (!res.ok) throw new Error(`Live forecast unavailable (${res.status})`);
    renderForecast(await res.json());
  } catch (err) {
    showResultError(el, err.message);
  }
}

function renderObservedSignals(obs, disease) {
  if (!obs) return "";
  const signals = [
    { label: "Rainfall", value: `${obs.rainfall} mm`, hint: "Observed feed" },
    { label: "Temperature", value: `${obs.temperature}°C`, hint: "Mean" },
    { label: "Humidity", value: `${obs.humidity}%`, hint: "Relative" },
    { label: "Reported cases", value: obs.current_cases, hint: `Previous period: ${obs.previous_cases}` },
  ];
  if (disease === "respiratory") {
    signals.push({ label: "Air quality", value: obs.aqi, hint: "AQI" });
  }
  return `<div class="his-signals">${signals.map((s) => `
    <div class="his-signal">
      <div class="his-signal__label">${s.label}</div>
      <div class="his-signal__value">${s.value}</div>
      <div class="his-signal__hint">${s.hint}</div>
    </div>`).join("")}</div>`;
}

function renderDistrictTable(districts) {
  if (!districts || !districts.length) return "";
  return `
    <div class="his-table-wrap">
      <table class="his-table">
        <caption>District risk ranking</caption>
        <thead>
          <tr>
            <th>Administrative unit</th>
            <th>Risk</th>
            <th>Trend</th>
            <th class="his-table__num">Reported cases</th>
            <th class="his-table__num">Surge probability</th>
          </tr>
        </thead>
        <tbody>
          ${districts.map((d) => `
            <tr>
              <td>${d.admin_unit}</td>
              <td>${d.risk_level}</td>
              <td>${d.risk_trend}</td>
              <td class="his-table__num">${d.current_cases}</td>
              <td class="his-table__num">${Math.round((d.surge_probability || 0) * 100)}%</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>`;
}

function renderForecast(payload) {
  const el = document.getElementById("forecast-result");
  if (!el) return;
  const fc = payload.forecast || payload;
  const month = MONTHS[(payload.start_month || 1) - 1];
  const cls = riskClass(fc.predicted_risk_level);
  const diseaseId = payload.disease || fc.disease;
  const disease = diseaseLabel(diseaseId);
  const unit = payload.admin_unit === "national" ? "National" : (payload.admin_unit || adminLabel("f-admin"));
  const onset = Math.round((fc.onset_likelihood || 0) * 100);
  const surge = Math.round((fc.surge_probability || 0) * 100);
  const conf = Math.round((fc.confidence || 0) * 100);
  setLiveStamp("forecast-live-stamp", payload.updated_at);

  el.innerHTML = `
    ${renderObservedSignals(payload.observed, diseaseId)}
    <div class="his-banner his-banner--${cls}">
      <div class="his-banner__mark" aria-hidden="true"></div>
      <div class="his-banner__body">
        <div class="his-banner__over">${disease} · ${unit} · ${payload.horizon_days || 28}-day horizon from ${month}</div>
        <div class="his-banner__title">Projected risk: ${fc.predicted_risk_level}</div>
        <div class="his-banner__sub">Peak transmission period: ${fc.peak_window} · Model confidence ${conf}%</div>
      </div>
    </div>
    <div class="his-kpi-row">
      <div class="his-kpi">
        <div class="his-kpi__label">Case trend</div>
        <div class="his-kpi__value">${fc.risk_trend}</div>
        <div class="his-kpi__hint">Current vs previous reporting period</div>
      </div>
      <div class="his-kpi">
        <div class="his-kpi__label">Probability of seasonal onset</div>
        <div class="his-kpi__value">${onset}%</div>
        <div class="his-kpi__bar"><span style="width:${onset}%"></span></div>
      </div>
      <div class="his-kpi">
        <div class="his-kpi__label">Probability of caseload surge</div>
        <div class="his-kpi__value">${surge}%</div>
        <div class="his-kpi__bar"><span style="width:${surge}%"></span></div>
      </div>
      <div class="his-kpi">
        <div class="his-kpi__label">Peak transmission window</div>
        <div class="his-kpi__value his-kpi__value--text">${fc.peak_window}</div>
        <div class="his-kpi__hint">Based on climatology for this disease</div>
      </div>
    </div>
    ${renderDistrictTable(payload.districts)}
    <div class="his-cols">
      <div class="his-block">
        <h3 class="his-block__title">Contributing factors</h3>
        <ol class="his-ol">${(fc.factors || []).map((f) => `<li>${f}</li>`).join("")}</ol>
      </div>
      <div class="his-block">
        <h3 class="his-block__title">Recommended actions</h3>
        <ol class="his-ol">${(fc.recommendations || []).map((f) => `<li>${f}</li>`).join("")}</ol>
      </div>
    </div>
    <p class="his-footnote">${payload.source || "Climate, surveillance and facility feeds"} · Outputs are planning estimates, not confirmed surveillance. Interpret with DHIS2 / IDSR and local epidemiology.</p>
  `;
}

async function loadLiveSurge() {
  const el = document.getElementById("surge-result");
  try {
    const res = await fetch(`${API}/healthcare/surge/live?${liveQuery("s-disease", "s-admin")}`);
    if (!res.ok) throw new Error(`Live capacity unavailable (${res.status})`);
    renderSurge(await res.json());
  } catch (err) {
    showResultError(el, err.message);
  }
}

function gapStatus(gap) {
  if (gap > 0) return { cls: "deficit", label: "Deficit" };
  if (gap < 0) return { cls: "surplus", label: "Surplus" };
  return { cls: "met", label: "Met" };
}

function renderSurge(data) {
  const el = document.getElementById("surge-result");
  if (!el) return;
  const expected = data.expected_surge_cases;
  const cls = riskClass(data.risk_level);
  const disease = diseaseLabel(data.disease);
  const unit = data.admin_unit === "national" ? "National" : (data.admin_unit || adminLabel("s-admin"));
  const increase = data.projected_increase_pct != null ? ` · projected increase ${data.projected_increase_pct}%` : "";
  setLiveStamp("surge-live-stamp", data.updated_at);
  const rows = [
    { label: "Hospitals", value: data.hospitals ?? "—" },
    { label: "Community health centres", value: data.chcs ?? "—" },
    { label: "Community health posts", value: data.chps ?? "—" },
    { label: "Clinics", value: data.clinics ?? "—" },
  ];

  el.innerHTML = `
    <div class="his-banner his-banner--${cls}">
      <div class="his-banner__mark" aria-hidden="true"></div>
      <div class="his-banner__body">
        <div class="his-banner__over">${disease} · ${unit} · ${data.facility_count || 0} MoH facilities · ${data.current_cases} current cases → ${expected} projected cases${increase}</div>
        <div class="his-banner__title">Projected risk: ${data.risk_level}</div>
        <div class="his-banner__sub">${data.cases_per_facility} projected cases per registered facility</div>
      </div>
    </div>
    <div class="his-kpi-row">
      ${rows.map((r) => `
        <div class="his-kpi">
          <div class="his-kpi__label">${r.label}</div>
          <div class="his-kpi__value">${r.value}</div>
          <div class="his-kpi__hint">MoH DHIS2 registry</div>
        </div>`).join("")}
    </div>
    <div class="his-block">
      <h3 class="his-block__title">Recommended actions</h3>
      <ol class="his-ol">${(data.recommendations || []).map((f) => `<li>${f}</li>`).join("")}</ol>
    </div>
    <p class="his-footnote">${data.source || ""} · ${data.note || "Bed, staffing and supply stocks are not in the MoH DHIS2 core facility registry."}</p>
  `;
}

document.getElementById("f-admin")?.addEventListener("change", loadLiveForecast);
document.getElementById("f-disease")?.addEventListener("change", loadLiveForecast);
document.getElementById("s-admin")?.addEventListener("change", loadLiveSurge);
document.getElementById("s-disease")?.addEventListener("change", loadLiveSurge);

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
  const types = summary.by_type || {};
  el("mfl-total", summary.total_facilities);
  el("mfl-hospitals", types.Hospital || 0);
  el("mfl-chcs", types.CHC || 0);
  el("mfl-chps", types.CHP || 0);
  el("mfl-districts", summary.districts_covered);
  el("mfl-flood-exposed", summary.flood_exposed_facilities);
  if (window.lucide) lucide.createIcons();
}

// --- Initialize Leaflet Map ---
function initMflMap() {
  if (mflMapInitialized) { updateMflMapMarkers(); return; }
  const mapEl = document.getElementById("mfl-map");
  if (!mapEl || !window.L) return;

  mflMap = L.map("mfl-map", { zoomControl: true, preferCanvas: true }).setView([8.46, -11.78], 7);
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

  const typeColors = {
    Hospital: "#ef4444",
    CHC: "#22c55e",
    CHP: "#6366f1",
    Clinic: "#f59e0b",
    Other: "#888888",
  };

  mflFacilities.forEach(f => {
    if (!f.latitude || !f.longitude) return;

    const color = typeColors[f.facility_type] || "#888888";
    const radius = f.facility_type === "Hospital" ? 7 : f.facility_type === "CHC" ? 5 : 4;

    const marker = L.circleMarker([f.latitude, f.longitude], {
      radius: radius,
      fillColor: color,
      color: "rgba(255,255,255,0.35)",
      weight: 1,
      fillOpacity: 0.8,
    });

    const id = String(f.facility_id).replace(/'/g, "\\'");
    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:200px">
        <div style="font-weight:700;font-size:0.85rem;margin-bottom:4px">${f.facility_name}</div>
        <div style="font-size:0.72rem;color:#888;margin-bottom:6px">${f.facility_code || f.facility_id} · ${f.facility_type} · ${f.district}</div>
        <div style="font-size:0.72rem;color:#aaa">DHIS2 coordinates</div>
        <button type="button" onclick="openFacilityProfile('${id}')" style="margin-top:8px;padding:4px 12px;font-size:0.72rem;background:#6366f1;color:white;border:none;border-radius:4px;cursor:pointer">View profile</button>
      </div>
    `);

    mflMarkers.addLayer(marker);
  });
}

// --- Render Facility Table ---
const MFL_PAGE_SIZE = 50;
let mflFiltered = [];
let mflPage = 1;

function typeBadgeClass(type) {
  const k = (type || "other").toLowerCase();
  return `mfl-type-badge mfl-type-badge--${k}`;
}

function escapeAttr(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function renderMflPager(total) {
  const el = document.getElementById("mfl-pager");
  if (!el) return;
  const pages = Math.max(1, Math.ceil(total / MFL_PAGE_SIZE));
  if (mflPage > pages) mflPage = pages;
  el.innerHTML = `
    <button type="button" class="btn btn--ghost btn--sm" ${mflPage <= 1 ? "disabled" : ""} onclick="mflGoPage(${mflPage - 1})">Prev</button>
    <span class="mfl-pager__label">Page ${mflPage} of ${pages}</span>
    <button type="button" class="btn btn--ghost btn--sm" ${mflPage >= pages ? "disabled" : ""} onclick="mflGoPage(${mflPage + 1})">Next</button>
  `;
}

function mflGoPage(p) {
  mflPage = p;
  renderMflTable(mflFiltered);
}
window.mflGoPage = mflGoPage;

function renderMflTable(facilities) {
  const tbody = document.getElementById("mfl-table-body");
  const countEl = document.getElementById("mfl-table-count");
  if (!tbody) return;
  mflFiltered = facilities;
  const total = facilities.length;
  if (countEl) countEl.textContent = `Showing ${total} facilities · MoH DHIS2 registry`;

  if (total === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:2rem;color:var(--text-dim)">No facilities match the current filters</td></tr>';
    renderMflPager(0);
    return;
  }

  const start = (mflPage - 1) * MFL_PAGE_SIZE;
  const pageRows = facilities.slice(start, start + MFL_PAGE_SIZE);

  tbody.innerHTML = pageRows.map(f => {
    const id = escapeAttr(f.facility_id);
    const coords = (f.latitude != null && f.longitude != null)
      ? `${Number(f.latitude).toFixed(3)}, ${Number(f.longitude).toFixed(3)}`
      : "—";
    return `
    <tr>
      <td style="font-family:monospace;font-size:0.72rem;color:var(--text-dim)">${f.facility_code || f.facility_id}</td>
      <td style="font-weight:600">${f.facility_name}</td>
      <td>${f.district}</td>
      <td><span class="${typeBadgeClass(f.facility_type)}">${f.facility_type}</span></td>
      <td class="his-table__num" style="text-align:left;font-weight:400">${coords}</td>
      <td><button class="btn btn--ghost btn--sm" onclick="openFacilityProfile('${id}')" style="font-size:0.7rem;padding:0.2rem 0.6rem">View</button></td>
    </tr>`;
  }).join("");
  renderMflPager(total);
  if (window.lucide) lucide.createIcons();
}

// --- Filters ---
function applyMflFilters() {
  const district = document.getElementById("mfl-district-filter").value;
  const type = document.getElementById("mfl-type-filter").value;
  const search = document.getElementById("mfl-search").value.toLowerCase().trim();

  let filtered = mflFacilities;
  if (district) filtered = filtered.filter(f => f.district === district);
  if (type) filtered = filtered.filter(f => f.facility_type === type);
  if (search) {
    filtered = filtered.filter(f =>
      f.facility_name.toLowerCase().includes(search) ||
      (f.district || "").toLowerCase().includes(search) ||
      (f.facility_id || "").toLowerCase().includes(search) ||
      (f.facility_code || "").toLowerCase().includes(search)
    );
  }

  mflPage = 1;
  renderMflTable(filtered);

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
  document.getElementById("mfl-search").value = "";
  mflPage = 1;
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
  const coords = (profile.latitude != null && profile.longitude != null)
    ? `${Number(profile.latitude).toFixed(5)}, ${Number(profile.longitude).toFixed(5)}`
    : "Data not available";
  const na = (v) => (v == null || v === "" ? "Data not available" : v);

  let html = `
    <div style="text-align:center;margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid var(--border)">
      <div style="font-size:1.3rem;font-weight:800;color:var(--text-bright)">${profile.facility_name}</div>
      <div style="font-size:0.78rem;color:var(--text-dim);margin-top:0.25rem">${profile.facility_code || profile.facility_id} · ${profile.facility_type} · ${profile.district}</div>
      <div style="font-size:0.72rem;color:var(--text-dim);margin-top:0.15rem">${profile.region || ""}</div>
      <div style="font-size:0.7rem;color:var(--text-dim);margin-top:0.35rem">Ministry of Health DHIS2 Master Facility List</div>
    </div>

    <div class="grid-3 mb-1">
      <div class="metric">
        <div class="metric__label">DHIS2 UID</div>
        <div class="metric__value" style="font-size:0.9rem">${na(profile.dhis2_uid)}</div>
      </div>
      <div class="metric">
        <div class="metric__label">Facility type</div>
        <div class="metric__value" style="font-size:0.9rem">${profile.facility_type}</div>
      </div>
      <div class="metric">
        <div class="metric__label">Coordinates</div>
        <div class="metric__value" style="font-size:0.85rem">${coords}</div>
      </div>
    </div>

    <div class="section-heading" style="margin-bottom:0.5rem">Not in this registry</div>
    <ul class="result-list" style="margin-bottom:1.25rem">
      ${(profile.key_gaps || []).map(g => `<li>${g}</li>`).join("")}
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
  loadLiveForecast();
  loadLiveSurge();
  setInterval(loadLiveForecast, LIVE_REFRESH_MS);
  setInterval(loadLiveSurge, LIVE_REFRESH_MS);
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
