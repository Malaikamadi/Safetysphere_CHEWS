
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
    html += `<div class="progress-bar mb-1"><div class="progress-bar__fill" style="width:${data.composite_score * 100}%;background:linear-gradient(90deg,var(--success),var(--warning),var(--danger))"></div></div>`;
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

const FLOOD_TABS = ["atlas", "vulnerability", "hazard", "pollution", "carbon"];

/** Parse hashes like `#atlas`, `#atlas/kroo_bay`, `#hazard`. */
function parsePlanningHash(hash) {
  const raw = (hash || "").replace(/^#/, "");
  if (!raw) return { tab: null, zoneId: null };
  const i = raw.indexOf("/");
  if (i === -1)
    return { tab: FLOOD_TABS.includes(raw) ? raw : null, zoneId: null };
  const tab = raw.slice(0, i);
  const zoneId = raw.slice(i + 1).trim();
  if (!FLOOD_TABS.includes(tab)) return { tab: null, zoneId: null };
  return { tab, zoneId: decodeURIComponent(zoneId) || null };
}

function syncAtlasHash(zoneIdOrNull) {
  const hash = zoneIdOrNull ? `#atlas/${encodeURIComponent(zoneIdOrNull)}` : "#atlas";
  const base = `${location.pathname}${location.search}`;
  try {
    history.replaceState(null, "", `${base}${hash}`);
  } catch (_) {
    location.hash = hash;
  }
}

// =====================================================================
// Flood Atlas — Sierra Leone
// =====================================================================
//
// Boots a Leaflet map of Sierra Leone, polls the live dashboard endpoint,
// renders one circle marker per flood-prone community colored by risk
// level, and wires up the scenario simulator + top-10 risk table +
// per-zone 24h forecast detail panel.
// =====================================================================

/** Matches --risk-band-* in styles.css (read at runtime so legend & markers stay aligned). */
const FLOOD_LEVEL_CSS_VAR = {
  Low: "--risk-band-low",
  Moderate: "--risk-band-moderate",
  High: "--risk-band-high",
  Severe: "--risk-band-severe",
  Extreme: "--risk-band-extreme",
};

const FLOOD_LEVEL_COLOR_FALLBACK = {
  Low: "#6b986f",
  Moderate: "#c9a963",
  High: "#c8875c",
  Severe: "#c75c54",
  Extreme: "#943d3a",
};

const FloodAtlas = {
  map: null,
  layer: null,            // L.layerGroup of circle markers
  zonesById: {},          // last snapshot keyed by zone id
  baselineKpis: null,     // first non-scenario snapshot, used for delta display
  selectedId: null,
  /** Set from URL `#atlas/zone_id`; consumed once after dashboard render. */
  _pendingZoneSelection: null,
  refreshTimer: null,
  scenarioActive: false,

  fmtInt(n) {
    return (n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
  },

  riskColor(level) {
    const vn = FLOOD_LEVEL_CSS_VAR[level];
    if (vn) {
      const raw = getComputedStyle(document.documentElement).getPropertyValue(vn).trim();
      if (raw) return raw;
    }
    return FLOOD_LEVEL_COLOR_FALLBACK[level] || "#908980";
  },

  riskRadius(score) {
    return 8 + score * 18;   // 8px..26px
  },

  init() {
    if (this.map || !window.L) return;
    const el = document.getElementById("flood-map");
    if (!el) return;

    this.map = L.map(el, {
      center: [8.46, -11.78],
      zoom: 7,
      minZoom: 6,
      maxZoom: 13,
      zoomControl: true,
      attributionControl: true,
    });

    // Carto Dark Matter tiles to match the dark UI.
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 19,
      }
    ).addTo(this.map);

    this.layer = L.layerGroup().addTo(this.map);

    // Wire up controls (idempotent, safe to call before first render).
    document.getElementById("atlas-refresh")?.addEventListener("click", () => this.refresh());

    const sc = (id) => document.getElementById(id);
    sc("sc-rain")?.addEventListener("input", (e) => sc("sc-rain-val").textContent = (+e.target.value).toFixed(1));
    sc("sc-rain24")?.addEventListener("input", (e) => sc("sc-rain24-val").textContent = (+e.target.value).toFixed(1));
    sc("sc-sat")?.addEventListener("input", (e) => sc("sc-sat-val").textContent = (e.target.value > 0 ? "+" : "") + e.target.value);
    sc("sc-run")?.addEventListener("click", () => this.runScenario());
    sc("sc-reset")?.addEventListener("click", () => {
      sc("sc-rain").value = 1.0; sc("sc-rain-val").textContent = "1.0";
      sc("sc-rain24").value = 1.0; sc("sc-rain24-val").textContent = "1.0";
      sc("sc-sat").value = 0; sc("sc-sat-val").textContent = "+0";
      this.scenarioActive = false;
      this.refresh();
    });

    // Auto-refresh while the Atlas tab is visible.
    this.refresh();
    this.refreshTimer = setInterval(() => {
      if (!this.scenarioActive && document.getElementById("tab-atlas") &&
        !document.getElementById("tab-atlas").classList.contains("hidden")) {
        this.refresh();
      }
    }, 30000);
  },

  async refresh() {
    try {
      const res = await fetch(`${API}/strategic/flood-dashboard`);
      if (!res.ok) throw new Error(`Server ${res.status}`);
      const snap = await res.json();
      if (!this.baselineKpis) this.baselineKpis = snap.kpis;
      this.scenarioActive = false;
      document.getElementById("sc-delta").innerHTML = "";
      this.render(snap);
    } catch (e) {
      console.warn("flood dashboard unreachable", e);
      const updated = document.getElementById("atlas-updated");
      if (updated) updated.textContent = "Backend offline — start uvicorn on :8000";
    }
  },

  async runScenario() {
    const body = {
      rainfall_intensity_mult: +document.getElementById("sc-rain").value,
      rainfall_24h_mult: +document.getElementById("sc-rain24").value,
      saturation_offset: +document.getElementById("sc-sat").value,
    };
    try {
      const res = await fetch(`${API}/strategic/flood-forecast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Server ${res.status}`);
      const snap = await res.json();
      this.scenarioActive = true;
      this.render(snap, body);
    } catch (e) {
      alert("Scenario request failed: " + e.message);
    }
  },

  render(snap, scenarioBody) {
    this.zonesById = {};
    snap.zones.forEach(z => this.zonesById[z.id] = z);

    // KPI cards
    const k = snap.kpis;
    document.getElementById("kpi-zones").textContent = this.fmtInt(k.zones_monitored);
    document.getElementById("kpi-districts").textContent = `across ${k.districts_monitored} districts`;
    document.getElementById("kpi-pop-risk").textContent = this.fmtInt(k.population_at_risk);
    document.getElementById("kpi-high").textContent = this.fmtInt(k.high_risk_zones);
    document.getElementById("kpi-severe").textContent = `${k.severe_zones} severe / mean risk ${k.mean_zone_risk.toFixed(2)}`;
    document.getElementById("kpi-rain").textContent = `${k.avg_rainfall_intensity_mm_h.toFixed(1)} mm/h`;
    document.getElementById("kpi-rain-24").textContent = (snap.districts.reduce((a, d) => a + d.rainfall_24h_mm, 0) / snap.districts.length).toFixed(0);
    document.getElementById("kpi-sat").textContent = `${k.avg_soil_saturation_pct.toFixed(0)}%`;
    document.getElementById("kpi-river").textContent = `${k.avg_river_stage_pct_bankfull.toFixed(0)}%`;

    const updated = document.getElementById("atlas-updated");
    if (updated) {
      const ts = new Date(snap.generated_at);
      const tag = this.scenarioActive ? "scenario" : "live";
      updated.textContent = `Updated ${ts.toLocaleTimeString()} · ${tag}`;
    }

    // Map markers
    if (this.layer) this.layer.clearLayers();
    snap.zones.forEach(z => {
      const color = this.riskColor(z.prediction.risk_level);
      const m = L.circleMarker([z.lat, z.lng], {
        radius: this.riskRadius(z.prediction.risk_score),
        color: color,
        weight: 2,
        opacity: 0.9,
        fillColor: color,
        fillOpacity: 0.55,
      });
      m.bindTooltip(`<strong>${z.name}</strong><br>${z.prediction.risk_level} · ${z.prediction.risk_score.toFixed(2)}`, { sticky: true });
      m.on("click", () => this.selectZone(z.id));
      m.addTo(this.layer);
    });

    if (snap.bounds && this.map && !this._fitted) {
      this.map.fitBounds([snap.bounds.south_west, snap.bounds.north_east], { padding: [20, 20] });
      this._fitted = true;
    }

    const metaEl = document.getElementById("atlas-meta");
    if (metaEl && snap.meta) {
      metaEl.style.display = "block";
      metaEl.textContent = `${snap.meta.signals_source}: ${snap.meta.catalog_notes}`;
    }

    // Top-10 table
    this.renderTable(snap.zones);

    // Scenario delta block
    if (scenarioBody && this.baselineKpis) {
      const dHigh = k.high_risk_zones - this.baselineKpis.high_risk_zones;
      const dPop = k.population_at_risk - this.baselineKpis.population_at_risk;
      const dMean = k.mean_zone_risk - this.baselineKpis.mean_zone_risk;
      const sign = (n) => n > 0 ? `+${n}` : `${n}`;
      document.getElementById("sc-delta").innerHTML = `
        <div class="scenario__delta-row"><span>Δ high-risk zones</span><strong class="${dHigh > 0 ? 'text-danger' : 'text-success'}">${sign(dHigh)}</strong></div>
        <div class="scenario__delta-row"><span>Δ population at risk</span><strong class="${dPop > 0 ? 'text-danger' : 'text-success'}">${sign(this.fmtInt(dPop))}</strong></div>
        <div class="scenario__delta-row"><span>Δ mean risk</span><strong class="${dMean > 0 ? 'text-danger' : 'text-success'}">${dMean >= 0 ? '+' : ''}${dMean.toFixed(3)}</strong></div>`;
    }

    // Refresh selected zone if one was open.
    if (this.selectedId && this.zonesById[this.selectedId]) {
      this.renderZoneDetail(this.zonesById[this.selectedId]);
    }

    if (this._pendingZoneSelection && this.zonesById[this._pendingZoneSelection]) {
      const pid = this._pendingZoneSelection;
      this._pendingZoneSelection = null;
      void this.selectZone(pid, true);
    }

    if (window.lucide) lucide.createIcons();
  },

  renderTable(zones) {
    const top = [...zones].sort((a, b) => b.prediction.risk_score - a.prediction.risk_score).slice(0, 10);
    const tbody = document.getElementById("zone-table-body");
    if (!tbody) return;
    tbody.innerHTML = top.map((z, i) => {
      const drivers = z.prediction.factors.slice(0, 2).join(" · ");
      const color = this.riskColor(z.prediction.risk_level);
      return `<tr data-zone="${z.id}">
        <td>${i + 1}</td>
        <td><strong>${z.name}</strong></td>
        <td>${z.district_name}</td>
        <td><span class="risk-pill" style="--risk-c:${color}">${z.prediction.risk_score.toFixed(2)}</span></td>
        <td>${z.prediction.risk_level}</td>
        <td>${this.fmtInt(z.population)}</td>
        <td class="text-dim">${drivers || "—"}</td>
      </tr>`;
    }).join("");
    tbody.querySelectorAll("tr[data-zone]").forEach(tr => {
      tr.addEventListener("click", () => this.selectZone(tr.dataset.zone));
    });
  },

  async selectZone(id, skipHashSync) {
    const z = this.zonesById[id];
    if (!z || !this.map) return;
    this.selectedId = id;
    if (!skipHashSync) syncAtlasHash(id);
    this.map.flyTo([z.lat, z.lng], Math.max(this.map.getZoom(), 11), { duration: 0.6 });
    this.renderZoneDetail(z);
    try {
      const res = await fetch(`${API}/strategic/flood-zone/${id}/forecast?hours=24`);
      if (!res.ok) return;
      const fc = await res.json();
      this.renderForecast(fc);
    } catch (_) { }
  },

  renderZoneDetail(z) {
    document.getElementById("zone-detail-hint").textContent = `${z.name}, ${z.district_name}`;
    const detail = document.getElementById("zone-detail");
    detail.style.display = "";
    const p = z.prediction;
    const color = this.riskColor(p.risk_level);
    detail.innerHTML = `
      <div class="zone-detail__head">
        <div>
          <div class="zone-detail__name">${z.name}</div>
          <div class="zone-detail__meta">${z.urban_type.replace(/_/g, " ")} · ${z.water_body}</div>
        </div>
        <div class="risk-badge" style="background:${color}22;color:${color};border:1px solid ${color}55">${p.risk_level} · ${p.risk_score.toFixed(2)}</div>
      </div>
      <div class="zone-detail__metrics">
        <div><div class="metric__label">Elevation</div><div class="metric__value">${z.elevation_m.toFixed(0)} m</div></div>
        <div><div class="metric__label">Drainage</div><div class="metric__value">${z.drainage_quality}</div></div>
        <div><div class="metric__label">Water dist.</div><div class="metric__value">${z.distance_to_water_km < 1 ? (z.distance_to_water_km * 1000).toFixed(0) + ' m' : z.distance_to_water_km.toFixed(1) + ' km'}</div></div>
        <div><div class="metric__label">Population</div><div class="metric__value">${this.fmtInt(z.population)}</div></div>
        <div><div class="metric__label">Rain now</div><div class="metric__value">${z.signal.rainfall_intensity_mm_h.toFixed(1)} mm/h</div></div>
        <div><div class="metric__label">Saturation</div><div class="metric__value">${z.signal.soil_saturation_pct.toFixed(0)}%</div></div>
      </div>
      <div class="zone-detail__bars">
        ${["rainfall", "terrain", "drainage", "proximity", "saturation"].map(k => `
          <div class="contrib"><span class="contrib__lbl">${k}</span><div class="contrib__track"><div class="contrib__fill" style="width:${(p.contributions[k] * 100).toFixed(0)}%;background:${color}"></div></div><span class="contrib__val">${(p.contributions[k] * 100).toFixed(0)}%</span></div>
        `).join("")}
      </div>
      <div class="zone-detail__rec">
        <div class="section-heading"><i data-lucide="check-circle"></i> Recommendations</div>
        <ul class="result-list result-list--success">${p.recommendations.map(r => `<li>${r}</li>`).join("")}</ul>
      </div>
      <div class="zone-detail__forecast" id="zone-forecast"></div>
    `;
    if (window.lucide) lucide.createIcons();
  },

  renderForecast(fc) {
    const el = document.getElementById("zone-forecast");
    if (!el) return;
    const rows = fc.hourly.map(h => {
      const c = this.riskColor(h.risk_level);
      const heightPct = Math.max(8, h.risk_score * 100);
      return `<div class="forecast-bar" title="+${h.hour_offset}h · ${h.risk_level} ${h.risk_score.toFixed(2)} · ${h.rainfall_intensity_mm_h.toFixed(1)} mm/h">
        <div class="forecast-bar__fill" style="height:${heightPct}%;background:${c}"></div>
        <span class="forecast-bar__label">+${h.hour_offset}</span>
      </div>`;
    }).join("");
    el.innerHTML = `
      <div class="section-heading"><i data-lucide="trending-up"></i> 24h forecast (hourly)</div>
      <div class="forecast-strip">${rows}</div>
    `;
    if (window.lucide) lucide.createIcons();
  },
};

// Boot the atlas the first time its tab becomes active.
function maybeBootAtlas() {
  if (!document.getElementById("tab-atlas")) return;
  if (document.getElementById("tab-atlas").classList.contains("hidden")) return;
  FloodAtlas.init();
  // Leaflet sometimes lays out wrong if the container was hidden — nudge it.
  setTimeout(() => FloodAtlas.map?.invalidateSize(), 50);
}

function applyPlanningHashFromUrl() {
  const { tab, zoneId } = parsePlanningHash(location.hash);
  FloodAtlas._pendingZoneSelection = tab === "atlas" && zoneId ? zoneId : null;
  if (tab) switchTab(tab);
}

window.addEventListener("DOMContentLoaded", () => {
  applyPlanningHashFromUrl();
  maybeBootAtlas();
});

window.addEventListener("hashchange", () => {
  applyPlanningHashFromUrl();
  if (parsePlanningHash(location.hash).tab === "atlas") maybeBootAtlas();
});

const _origSwitchTab = switchTab;
switchTab = function (tab) {
  _origSwitchTab(tab);
  if (tab === "atlas") {
    maybeBootAtlas();
    if (!parsePlanningHash(location.hash).zoneId)
      syncAtlasHash(null);
  }
};
