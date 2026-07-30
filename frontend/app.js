/**
 * CHEWS v3.0 — National Situation Room
 * =====================================
 * Modular architecture powering the full Situation Room:
 * Map, Timeline, AI Explainability, Scenario Simulator,
 * Community Intelligence, Sensor Network, Digital Twins,
 * and Decision Support Engine.
 */

const API_BASE = "http://localhost:8000";

// ==================== Utilities ====================

function animateCounter(el, from, to, duration, decimals = 0) {
  if (!el) return;
  const start = performance.now();
  function tick(now) {
    const p = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    const v = from + (to - from) * eased;
    el.textContent = decimals > 0 ? v.toFixed(decimals) : Math.round(v).toLocaleString();
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function riskClass(level) {
  if (!level) return "";
  const l = level.toLowerCase();
  if (l === "extreme" || l === "critical") return "risk--extreme";
  if (l === "high") return "risk--high";
  if (l === "moderate" || l === "medium") return "risk--moderate";
  return "risk--low";
}

function riskColor(score) {
  if (score >= 0.8) return "#943d3a";
  if (score >= 0.6) return "#c8875c";
  if (score >= 0.4) return "#c9a963";
  if (score >= 0.2) return "#6b986f";
  return "#4a7a4f";
}

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

// ==================== Smooth Scroll for Sidebar Anchors ====================

document.querySelectorAll('.sidebar__nav a[href^="#"]').forEach(link => {
  link.addEventListener("click", (e) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      // Update active state
      document.querySelectorAll(".sidebar__nav .nav-link").forEach(n => n.classList.remove("nav-link--active"));
      link.classList.add("nav-link--active");
      if (sidebar) sidebar.classList.remove("sidebar--open");
    }
  });
});

// ==================== 1. Situation Room Data ====================

async function loadSituationRoom() {
  // Update profile
  const roleDetails = typeof getRoleDetails !== "undefined" ? getRoleDetails() : null;
  if (roleDetails) {
    const avatarEl = document.getElementById("topbar-avatar");
    const nameEl = document.getElementById("topbar-name");
    const roleEl = document.getElementById("topbar-role-label");
    if (avatarEl) avatarEl.textContent = roleDetails.initials;
    if (nameEl) nameEl.textContent = roleDetails.fullName;
    if (roleEl) roleEl.textContent = roleDetails.subtitle;
  }

  // Update timestamp
  const tsEl = document.getElementById("topbar-timestamp");
  if (tsEl) {
    const now = new Date();
    tsEl.textContent = `Last updated: ${now.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}, ${now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
  }

  const srRiskScore = document.getElementById("sr-risk-score");
  if (!srRiskScore) return;

  try {
    const res = await fetch(`${API_BASE}/situation-room`);
    const data = await res.json();

    // Risk score
    const riskScore = data.national_risk_score || 0.68;
    srRiskScore.textContent = riskScore.toFixed(2);
    const riskBadge = document.getElementById("sr-risk-badge");
    if (riskBadge) {
      riskBadge.textContent = data.national_risk_level || "High Risk";
      const level = (data.national_risk_level || "high").toLowerCase();
      riskBadge.className = `na-kpi-card__badge na-kpi-card__badge--${level === "extreme" || level === "critical" || level === "high" ? "high" : level === "moderate" || level === "medium" ? "medium" : "low"}`;
    }

    // KPI Values
    const popRisk = data.population_at_risk || 1200000;
    const childrenRisk = data.children_at_risk || 412000;
    const pregnantRisk = data.pregnant_women_at_risk || 89000;
    const alertCount = data.active_alerts || 7;

    const popEl = document.getElementById("sr-population-risk");
    const childEl = document.getElementById("sr-children-risk");
    const pregEl = document.getElementById("sr-pregnant-risk");
    const alertEl = document.getElementById("sr-alert-count");

    if (popEl) popEl.textContent = formatLargeNumber(popRisk);
    if (childEl) childEl.textContent = formatLargeNumber(childrenRisk);
    if (pregEl) pregEl.textContent = formatLargeNumber(pregnantRisk);
    if (alertEl) alertEl.textContent = alertCount;

    // District Rankings Table
    const rankingsContainer = document.getElementById("sr-district-rankings");
    if (rankingsContainer) {
      rankingsContainer.innerHTML = "";
      const rankings = [
        { name: "Koinadugu", score: 0.82, risk: "Flood + Malaria", level: "high" },
        { name: "Bombali", score: 0.76, risk: "Flood", level: "high" },
        { name: "Port Loko", score: 0.72, risk: "Malaria", level: "med" },
        { name: "Kenema", score: 0.68, risk: "Malaria", level: "med" },
        { name: "Bo", score: 0.65, risk: "Malaria", level: "med" },
      ];
      rankings.forEach(d => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${d.name}</td>
          <td><span class="na-district-score na-district-score--${d.level}">${d.score.toFixed(2)}</span></td>
          <td><span class="na-district-badge na-district-badge--${d.level}">${d.risk}</span></td>
        `;
        rankingsContainer.appendChild(tr);
      });
    }

    // Active Alerts Feed
    const alertsFeed = document.getElementById("sr-alerts-feed");
    if (alertsFeed) {
      const alerts = data.recommended_actions || [
        { action: "Flood risk high in Koinadugu", priority: "high", icon: "waves", time: "3 hours ago" },
        { action: "Malaria surge predicted", priority: "high", icon: "bug", time: "5 hours ago" },
        { action: "Air quality unhealthy - Freetown", priority: "medium", icon: "cloud", time: "8 hours ago" },
        { action: "Heatwave expected next week", priority: "medium", icon: "thermometer", time: "12 hours ago" },
      ];
      alertsFeed.innerHTML = "";
      alerts.forEach(a => {
        const severity = a.priority === "critical" || a.priority === "high" ? "high" : "medium";
        const el = document.createElement("div");
        el.className = `na-alert-item na-alert-item--${severity}`;
        el.innerHTML = `
          <div class="na-alert-item__badge">${severity}</div>
          <div class="na-alert-item__content">
            <div class="na-alert-item__title">${a.action}</div>
            <div class="na-alert-item__meta">${a.time || "Recently"}</div>
          </div>
        `;
        alertsFeed.appendChild(el);
      });
    }

    // Decision Center
    const decisionsContainer = document.getElementById("sr-decisions");
    if (decisionsContainer) {
      decisionsContainer.innerHTML = "";
      const decisions = [
        { action: "Deploy mobile clinics to 12 high-risk communities", priority: "Critical Priority", impact: "86,000 people affected", timeline: "Estimated resources: 4 teams, 3,000 nets", level: "critical" },
        { action: "Pre-position medical supplies in Bombali district", priority: "High Priority", impact: "23,000 people at risk", timeline: "72-hour deployment window", level: "high" },
      ];
      decisions.forEach(d => {
        const el = document.createElement("div");
        el.className = `na-decision-card na-decision-card--${d.level}`;
        el.innerHTML = `
          <div class="na-decision-card__badge">${d.priority}</div>
          <div class="na-decision-card__content">
            <div class="na-decision-card__action">${d.action}</div>
            <div class="na-decision-card__meta">
              <span><i data-lucide="target"></i> ${d.impact}</span>
              <span><i data-lucide="clock"></i> ${d.timeline}</span>
            </div>
          </div>
        `;
        decisionsContainer.appendChild(el);
      });
    }

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Failed to load situation room data", err);
    srRiskScore.textContent = "--";
  }
}

function formatLargeNumber(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1).replace(".0", "") + "M";
  if (num >= 1000) return (num / 1000).toFixed(0) + "K";
  return num.toLocaleString();
}


// ==================== 2. Interactive Map ====================

let srMap = null;
let mapLayers = {};
let mapData = null;

async function initMap() {
  const mapEl = document.getElementById("sr-map");
  if (!mapEl) return;

  srMap = L.map("sr-map", {
    center: [8.46, -11.78],
    zoom: 7,
    zoomControl: true,
    attributionControl: true,
  });

  // Dark-themed tile layer
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://openstreetmap.org">OSM</a>',
    maxZoom: 18,
  }).addTo(srMap);

  try {
    const res = await fetch(`${API_BASE}/situation-room/map-data`);
    mapData = await res.json();
    renderMapLayers(mapData);
    setupLayerToggles();
  } catch (err) {
    console.error("Failed to load map data", err);
  }
}

function renderMapLayers(data) {
  if (!srMap || !data || !data.layers) return;

  const layerRenderers = {
    flood: (features) => renderHeatCircles(features, "#6f8faa", 28),
    malaria: (features) => renderHeatCircles(features, "#c75c54", 28),
    heat: (features) => renderHeatCircles(features, "#c4876a", 24),
    air_quality: (features) => renderHeatCircles(features, "#9c7f8f", 24),
    vulnerability: (features) => renderHeatCircles(features, "#c9a963", 22),
    carbon: (features) => renderHeatCircles(features, "#4a6b51", 20),
    facilities: (features) => renderMarkers(features, "#7d9f86", "hospital"),
    schools: (features) => renderMarkers(features, "#c9a35c", "school"),
    sensors: (features) => renderSensorMarkers(features),
    community_reports: (features) => renderReportMarkers(features),
  };

  Object.entries(data.layers).forEach(([layerName, fc]) => {
    if (layerRenderers[layerName]) {
      mapLayers[layerName] = layerRenderers[layerName](fc.features);
    }
  });

  // Show default layers
  const defaults = ["flood", "malaria", "facilities", "community_reports", "sensors"];
  defaults.forEach(name => {
    if (mapLayers[name]) mapLayers[name].addTo(srMap);
  });
}

function renderHeatCircles(features, color, baseRadius) {
  const group = L.layerGroup();
  features.forEach(f => {
    const coords = f.geometry.coordinates;
    const score = f.properties.score || 0.3;
    const circle = L.circleMarker([coords[1], coords[0]], {
      radius: baseRadius * (0.5 + score * 0.8),
      fillColor: f.properties.color || color,
      color: "transparent",
      fillOpacity: 0.45 + score * 0.3,
      weight: 0,
    });
    circle.bindTooltip(
      `<strong>${f.properties.name}</strong><br/>${f.properties.layer}: ${f.properties.risk_level} (${(score * 100).toFixed(0)}%)`,
      { direction: "top" }
    );
    group.addLayer(circle);
  });
  return group;
}

function renderMarkers(features, color, type) {
  const group = L.layerGroup();
  features.forEach(f => {
    const coords = f.geometry.coordinates;
    const marker = L.circleMarker([coords[1], coords[0]], {
      radius: 7,
      fillColor: color,
      color: "#fff",
      fillOpacity: 0.9,
      weight: 2,
    });
    let tooltip = `<strong>${f.properties.name}</strong>`;
    if (f.properties.beds) tooltip += `<br/>Beds: ${f.properties.beds} | Staff: ${f.properties.staff}`;
    marker.bindTooltip(tooltip, { direction: "top" });
    group.addLayer(marker);
  });
  return group;
}

function renderSensorMarkers(features) {
  const group = L.layerGroup();
  features.forEach(f => {
    const coords = f.geometry.coordinates;
    const online = f.properties.online;
    const marker = L.circleMarker([coords[1], coords[0]], {
      radius: 6,
      fillColor: online ? "#729e75" : "#943d3a",
      color: online ? "#afd4b2" : "#c75c54",
      fillOpacity: 0.85,
      weight: 2,
    });
    marker.bindTooltip(
      `<strong>${f.properties.name}</strong><br/>Status: ${online ? "🟢 Online" : "🔴 Offline"}`,
      { direction: "top" }
    );
    group.addLayer(marker);
  });
  return group;
}

function renderReportMarkers(features) {
  const group = L.layerGroup();
  const categoryColors = {
    vector: "#c75c54", flood: "#6f8faa", supply: "#c9a35c",
    disease: "#c4876a", water: "#7d9f86", environmental: "#9c7f8f",
  };
  features.forEach(f => {
    const coords = f.geometry.coordinates;
    const color = categoryColors[f.properties.category] || "#b5726b";
    const marker = L.circleMarker([coords[1], coords[0]], {
      radius: 5,
      fillColor: color,
      color: color,
      fillOpacity: 0.7,
      weight: 1,
    });
    marker.bindTooltip(
      `<strong>${f.properties.label}</strong><br/>${f.properties.district} · ${f.properties.hours_ago}h ago`,
      { direction: "top" }
    );
    group.addLayer(marker);
  });
  return group;
}

function setupLayerToggles() {
  document.querySelectorAll("input[data-layer]").forEach(checkbox => {
    checkbox.addEventListener("change", () => {
      const layerName = checkbox.dataset.layer;
      if (!mapLayers[layerName]) return;
      if (checkbox.checked) {
        mapLayers[layerName].addTo(srMap);
      } else {
        srMap.removeLayer(mapLayers[layerName]);
      }
    });
  });
}

// ==================== 3. Timeline Controller ====================

function initTimeline() {
  const slider = document.getElementById("sr-timeline-slider");
  if (!slider) return;

  slider.addEventListener("input", async () => {
    const val = parseInt(slider.value);

    // Update tick styling
    document.querySelectorAll(".sr-timeline__ticks span").forEach(tick => {
      tick.classList.toggle("sr-timeline__tick--active", parseInt(tick.dataset.val) === val);
    });

    await updateTimeline(val);
  });
}

async function updateTimeline(dayOffset) {
  try {
    const res = await fetch(`${API_BASE}/situation-room/timeline/${dayOffset}`);
    const data = await res.json();

    // Update summary
    document.getElementById("tl-flood").textContent = (data.summary.avg_flood_risk * 100).toFixed(0) + "%";
    document.getElementById("tl-malaria").textContent = (data.summary.avg_malaria_risk * 100).toFixed(0) + "%";
    document.getElementById("tl-districts").textContent = data.summary.districts_high_risk;
    document.getElementById("tl-facilities").textContent = data.summary.facilities_at_risk;

    // Update map circles if map exists
    if (srMap && mapLayers.flood) {
      srMap.removeLayer(mapLayers.flood);
      const floodFeatures = data.districts.map(d => ({
        type: "Feature",
        properties: { name: d.name, layer: "flood", score: d.flood_risk, risk_level: "", color: d.flood_color },
        geometry: { type: "Point", coordinates: [d.lng, d.lat] },
      }));
      mapLayers.flood = renderHeatCircles(floodFeatures, "#6f8faa", 28);
      const floodCheckbox = document.querySelector('input[data-layer="flood"]');
      if (floodCheckbox && floodCheckbox.checked) mapLayers.flood.addTo(srMap);
    }

    if (srMap && mapLayers.malaria) {
      srMap.removeLayer(mapLayers.malaria);
      const malariaFeatures = data.districts.map(d => ({
        type: "Feature",
        properties: { name: d.name, layer: "malaria", score: d.malaria_risk, risk_level: "", color: d.malaria_color },
        geometry: { type: "Point", coordinates: [d.lng, d.lat] },
      }));
      mapLayers.malaria = renderHeatCircles(malariaFeatures, "#c75c54", 28);
      const malariaCheckbox = document.querySelector('input[data-layer="malaria"]');
      if (malariaCheckbox && malariaCheckbox.checked) mapLayers.malaria.addTo(srMap);
    }
  } catch (err) {
    console.error("Timeline fetch failed", err);
  }
}

// ==================== 4. AI Explainability ====================

function initAIExplain() {
  document.querySelectorAll(".sr-ai-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".sr-ai-tab").forEach(t => t.classList.remove("sr-ai-tab--active"));
      tab.classList.add("sr-ai-tab--active");
      loadAIExplain(tab.dataset.hazard);
    });
  });

  loadAIExplain("malaria");
}

async function loadAIExplain(hazardType) {
  try {
    const res = await fetch(`${API_BASE}/situation-room/ai-explain/${hazardType}`);
    const data = await res.json();

    document.getElementById("ai-hazard-name").textContent = data.hazard;
    const badge = document.getElementById("ai-risk-badge");
    badge.textContent = data.risk_level;
    badge.className = `sr-ai-risk-display__badge sr-ai-risk-display__badge--${data.risk_level.toLowerCase()}`;
    document.getElementById("ai-confidence").textContent = `${data.confidence}%`;

    // Reasoning chain
    const reasoningEl = document.getElementById("ai-reasoning");
    reasoningEl.innerHTML = '<div class="sr-ai-reasoning__title">Reasoning Chain</div>';
    data.reasoning.forEach(r => {
      const item = document.createElement("div");
      item.className = `sr-ai-reason sr-ai-reason--${r.impact}`;
      item.innerHTML = `
        <span class="sr-ai-reason__indicator"></span>
        <span class="sr-ai-reason__text">${r.factor}</span>
      `;
      reasoningEl.appendChild(item);
    });

    // Contributors
    const contribEl = document.getElementById("ai-contributors");
    contribEl.innerHTML = "";
    data.contributors.forEach(c => {
      const bar = document.createElement("div");
      bar.className = "sr-ai-contrib";
      bar.innerHTML = `
        <div class="sr-ai-contrib__label">${c.name}</div>
        <div class="sr-ai-contrib__track">
          <div class="sr-ai-contrib__fill" style="width: 0%; background: ${c.color};"></div>
        </div>
        <div class="sr-ai-contrib__pct">${c.pct}%</div>
      `;
      contribEl.appendChild(bar);
      // Animate fill
      requestAnimationFrame(() => {
        setTimeout(() => {
          bar.querySelector(".sr-ai-contrib__fill").style.width = `${c.pct}%`;
        }, 50);
      });
    });

    // Model info
    const modelInfo = document.getElementById("ai-model-info");
    modelInfo.innerHTML = `
      <div class="sr-ai-model-info__item"><span>Model</span><strong>${data.model_version}</strong></div>
      <div class="sr-ai-model-info__item"><span>Training Data</span><strong>${data.training_data}</strong></div>
      <div class="sr-ai-model-info__item"><span>Last Retrained</span><strong>${data.last_retrained}</strong></div>
    `;

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("AI explain fetch failed", err);
  }
}

// ==================== 5. Scenario Simulator ====================

function initScenario() {
  const rainfallSlider = document.getElementById("sc-rainfall");
  const tempSlider = document.getElementById("sc-temp");
  const humiditySlider = document.getElementById("sc-humidity");
  const runBtn = document.getElementById("sc-run");

  if (!runBtn) return;

  // Update labels on slider input
  const updateLabels = () => {
    document.getElementById("sc-rainfall-val").textContent = `+${rainfallSlider.value}%`;
    document.getElementById("sc-temp-val").textContent = `+${tempSlider.value}°C`;
    document.getElementById("sc-humidity-val").textContent = `${humiditySlider.value}%`;
  };

  [rainfallSlider, tempSlider, humiditySlider].forEach(s => {
    if (s) s.addEventListener("input", updateLabels);
  });

  runBtn.addEventListener("click", runScenario);
}

async function runScenario() {
  const outputEl = document.getElementById("sc-output");
  outputEl.innerHTML = '<div class="sr-scenario__loading"><i data-lucide="loader-2" class="spin"></i> Running scenario...</div>';
  if (window.lucide) lucide.createIcons();

  try {
    const res = await fetch(`${API_BASE}/situation-room/scenario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rainfall_increase_pct: parseFloat(document.getElementById("sc-rainfall").value),
        temperature_increase_c: parseFloat(document.getElementById("sc-temp").value),
        humidity_pct: parseFloat(document.getElementById("sc-humidity").value),
        population_movement: document.getElementById("sc-pop-movement").value,
      }),
    });
    const data = await res.json();

    const o = data.outputs;
    outputEl.innerHTML = `
      <div class="sr-scenario__result-grid">
        <div class="sr-scenario__result sr-scenario__result--${o.flood_risk.level.toLowerCase()}">
          <div class="sr-scenario__result-label">Flood Risk</div>
          <div class="sr-scenario__result-value">${o.flood_risk.level}</div>
        </div>
        <div class="sr-scenario__result sr-scenario__result--${o.malaria_risk.level.toLowerCase()}">
          <div class="sr-scenario__result-label">Malaria</div>
          <div class="sr-scenario__result-value">${o.malaria_risk.level}</div>
        </div>
        <div class="sr-scenario__result">
          <div class="sr-scenario__result-label">Facilities Impacted</div>
          <div class="sr-scenario__result-value">${o.facilities_impacted}</div>
        </div>
        <div class="sr-scenario__result">
          <div class="sr-scenario__result-label">Roads Blocked</div>
          <div class="sr-scenario__result-value">${o.roads_blocked}</div>
        </div>
        <div class="sr-scenario__result">
          <div class="sr-scenario__result-label">Population Exposed</div>
          <div class="sr-scenario__result-value">${o.population_exposed.toLocaleString()}</div>
        </div>
      </div>
      <div class="sr-scenario__suggestion">
        <i data-lucide="lightbulb"></i>
        <span>${data.suggested_actions[0]}</span>
      </div>
      ${data.facility_impacts.length > 0 ? `
        <div class="sr-scenario__facility-impacts">
          <div class="sr-scenario__facility-title">Facility Impact Projection</div>
          ${data.facility_impacts.map(f => `
            <div class="sr-scenario__facility-row">
              <span class="sr-scenario__facility-name">${f.name}</span>
              <div class="sr-scenario__facility-bar-wrap">
                <div class="sr-scenario__facility-bar-baseline" style="width:${f.baseline_preparedness}%"></div>
                <div class="sr-scenario__facility-bar-projected" style="width:${f.projected_preparedness}%"></div>
              </div>
              <span class="sr-scenario__facility-change ${f.change < 0 ? "text-danger" : ""}">${f.change > 0 ? "+" : ""}${f.change}%</span>
            </div>
          `).join("")}
        </div>
      ` : ""}
    `;

    // -- Wow Moment Map Integration --
    if (srMap) {
      // Rain Overlay
      const rainVal = parseFloat(document.getElementById("sc-rainfall").value);
      const mapWrapper = document.querySelector(".sr-map-wrapper");
      if (mapWrapper) {
        let overlay = mapWrapper.querySelector(".weather-overlay");
        if (!overlay) {
          overlay = document.createElement("div");
          overlay.className = "weather-overlay weather-overlay--rain";
          mapWrapper.appendChild(overlay);
        }
        overlay.style.opacity = rainVal > 20 ? "1" : "0";
      }

      // District Impacts (Glow and Expand)
      if (data.district_impacts) {
        if (mapLayers.flood) {
          srMap.removeLayer(mapLayers.flood);
          const floodFeatures = data.district_impacts.map(d => ({
            type: "Feature",
            properties: { name: d.name, layer: "flood", score: d.flood_risk, risk_level: "", color: d.flood_color },
            geometry: { type: "Point", coordinates: [d.lng, d.lat] },
          }));
          mapLayers.flood = renderHeatCircles(floodFeatures, "#6f8faa", 28);
          mapLayers.flood.eachLayer(layer => {
            if (layer.feature && layer.feature.properties.score > 0.6) {
              if (layer._path) layer._path.classList.add("layer-glow");
            }
          });
          const floodCheckbox = document.querySelector('input[data-layer="flood"]');
          if (floodCheckbox && floodCheckbox.checked) mapLayers.flood.addTo(srMap);
        }

        if (mapLayers.malaria) {
          srMap.removeLayer(mapLayers.malaria);
          const malariaFeatures = data.district_impacts.map(d => ({
            type: "Feature",
            properties: { name: d.name, layer: "malaria", score: d.malaria_risk, risk_level: "", color: d.malaria_color },
            geometry: { type: "Point", coordinates: [d.lng, d.lat] },
          }));
          mapLayers.malaria = renderHeatCircles(malariaFeatures, "#c75c54", 28);
          mapLayers.malaria.eachLayer(layer => {
            if (layer.feature && layer.feature.properties.score > 0.6) {
              if (layer._path) layer._path.classList.add("layer-glow");
            }
          });
          const malariaCheckbox = document.querySelector('input[data-layer="malaria"]');
          if (malariaCheckbox && malariaCheckbox.checked) mapLayers.malaria.addTo(srMap);
        }
      }

      // Facility Impact Markers
      if (data.facility_impacts && mapLayers.facilities) {
        srMap.removeLayer(mapLayers.facilities);
        const fGroup = L.layerGroup();
        data.facility_impacts.forEach(f => {
          const color = f.projected_preparedness > 75 ? "#7d9f86" : (f.projected_preparedness > 50 ? "#c9a35c" : "#943d3a");
          const marker = L.circleMarker([f.lat, f.lng], {
            radius: 8, fillColor: color, color: "#fff", fillOpacity: 0.9, weight: 2
          });
          marker.bindTooltip(`<strong>${f.name}</strong><br/>Projected Preparedness: ${f.projected_preparedness}%`, { direction: "top" });
          fGroup.addLayer(marker);
        });
        mapLayers.facilities = fGroup;
        const facCheckbox = document.querySelector('input[data-layer="facilities"]');
        if (facCheckbox && facCheckbox.checked) mapLayers.facilities.addTo(srMap);
      }
    }

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    outputEl.innerHTML = `<div class="sr-scenario__output-placeholder">Error running scenario. Is the backend running?</div>`;
  }
}

// ==================== Live Ping Simulation ====================
function startCommunityPings() {
  if (!srMap || !mapLayers.community_reports) return;
  
  setInterval(() => {
    const lat = 8.46 + (Math.random() - 0.5) * 1.5;
    const lng = -11.78 + (Math.random() - 0.5) * 1.5;
    
    const ping = L.circleMarker([lat, lng], {
      radius: 5,
      fillColor: "#c75c54",
      color: "#c75c54",
      fillOpacity: 0.8,
      weight: 1,
      className: "ping-ring"
    }).addTo(srMap);
    
    setTimeout(() => {
      srMap.removeLayer(ping);
    }, 1500);
  }, 4000);
}

// ==================== 6. Community Intelligence ====================

async function loadCommunityIntel() {
  const feedEl = document.getElementById("cr-feed");
  const clustersEl = document.getElementById("cr-clusters");
  if (!feedEl) return;

  try {
    const res = await fetch(`${API_BASE}/situation-room/community-reports`);
    const data = await res.json();

    document.getElementById("cr-count").textContent = data.total_reports_24h;

    // Clusters
    const categoryIcons = { vector: "bug", flood: "waves", supply: "pill", disease: "thermometer", water: "droplets", environmental: "skull" };
    const categoryColors = { vector: "#c75c54", flood: "#6f8faa", supply: "#c9a35c", disease: "#c4876a", water: "#7d9f86", environmental: "#9c7f8f" };

    clustersEl.innerHTML = "";
    data.clusters.forEach(c => {
      const el = document.createElement("div");
      el.className = `sr-cluster ${c.trending ? "sr-cluster--trending" : ""}`;
      el.innerHTML = `
        <div class="sr-cluster__icon" style="color:${categoryColors[c.category] || "#b5726b"}"><i data-lucide="${categoryIcons[c.category] || "alert-circle"}"></i></div>
        <div class="sr-cluster__info">
          <div class="sr-cluster__name">${c.category.charAt(0).toUpperCase() + c.category.slice(1)}</div>
          <div class="sr-cluster__meta">${c.count} reports · ${c.districts_affected} districts</div>
        </div>
        ${c.trending ? '<div class="sr-cluster__badge">Trending ↑</div>' : ""}
      `;
      clustersEl.appendChild(el);
    });

    // Feed (latest 12)
    feedEl.innerHTML = "";
    data.reports.slice(0, 12).forEach(r => {
      const el = document.createElement("div");
      el.className = "sr-report";
      el.innerHTML = `
        <div class="sr-report__icon" style="color:${categoryColors[r.category] || "#b5726b"}"><i data-lucide="${r.icon}"></i></div>
        <div class="sr-report__content">
          <div class="sr-report__label">${r.label}</div>
          <div class="sr-report__meta">${r.district} · ${r.reporter} · ${r.hours_ago}h ago ${r.verified ? '<span class="sr-report__verified">✓ Verified</span>' : ""}</div>
        </div>
      `;
      feedEl.appendChild(el);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Community reports fetch failed", err);
  }
}

// ==================== 7. Sensor Network ====================

async function loadSensors() {
  const gridEl = document.getElementById("sr-sensors");
  if (!gridEl) return;

  try {
    const res = await fetch(`${API_BASE}/situation-room/sensors`);
    const data = await res.json();

    document.getElementById("sensor-online").textContent = data.online;
    document.getElementById("sensor-total").textContent = data.total;

    gridEl.innerHTML = "";
    data.sensors.forEach(s => {
      const el = document.createElement("div");
      el.className = `sr-sensor-card ${s.online ? "" : "sr-sensor-card--offline"}`;
      el.innerHTML = `
        <div class="sr-sensor-card__header">
          <div class="sr-sensor-card__name">${s.name}</div>
          <div class="sr-sensor-card__status ${s.online ? "sr-sensor-card__status--online" : "sr-sensor-card__status--offline"}">${s.online ? "ONLINE" : "OFFLINE"}</div>
        </div>
        <div class="sr-sensor-card__readings">
          <div class="sr-sensor-reading"><span class="sr-sensor-reading__label">Temperature</span><span class="sr-sensor-reading__value">${s.readings.temperature}°C</span></div>
          <div class="sr-sensor-reading"><span class="sr-sensor-reading__label">Humidity</span><span class="sr-sensor-reading__value">${s.readings.humidity}%</span></div>
          <div class="sr-sensor-reading"><span class="sr-sensor-reading__label">River</span><span class="sr-sensor-reading__value ${s.readings.river_level === "High" || s.readings.river_level === "Critical" ? "text-danger" : ""}">${s.readings.river_level}</span></div>
          <div class="sr-sensor-reading"><span class="sr-sensor-reading__label">AQI</span><span class="sr-sensor-reading__value">${s.readings.aqi}</span></div>
        </div>
        <div class="sr-sensor-card__footer">
          <span><i data-lucide="battery"></i> ${s.battery_pct}%</span>
          <span><i data-lucide="signal"></i> ${s.signal_strength}</span>
          <span>${s.last_reading}</span>
        </div>
        ${s.estimated ? '<div class="sr-sensor-card__estimated"><i data-lucide="info"></i> AI-estimated from nearby stations</div>' : ""}
      `;
      gridEl.appendChild(el);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Sensor fetch failed", err);
  }
}

// ==================== 8. Healthcare Digital Twins ====================

async function loadDigitalTwins() {
  const gridEl = document.getElementById("sr-twins");
  if (!gridEl) return;

  try {
    const res = await fetch(`${API_BASE}/situation-room/digital-twins`);
    const data = await res.json();

    gridEl.innerHTML = "";
    data.facilities.forEach(f => {
      const el = document.createElement("div");
      el.className = "sr-twin-card";

      const prepColor = riskColor(1 - f.preparedness / 100);
      const dashOffset = 251 - (f.preparedness / 100) * 251;

      el.innerHTML = `
        <div class="sr-twin-card__header">
          <div class="sr-twin-card__name">${f.name}</div>
          <div class="sr-twin-card__type">${f.type.replace("_", " ")}</div>
        </div>
        <div class="sr-twin-card__gauge">
          <svg viewBox="0 0 90 90" class="sr-twin-gauge">
            <circle cx="45" cy="45" r="40" fill="none" stroke="var(--border)" stroke-width="6" />
            <circle cx="45" cy="45" r="40" fill="none" stroke="${prepColor}" stroke-width="6"
                    stroke-dasharray="251" stroke-dashoffset="${dashOffset}"
                    stroke-linecap="round" transform="rotate(-90 45 45)"
                    class="sr-twin-gauge__arc" />
            <text x="45" y="45" text-anchor="middle" dominant-baseline="central"
                  fill="var(--text-bright)" font-size="18" font-weight="700">${f.preparedness}%</text>
          </svg>
          <div class="sr-twin-card__gauge-label">Preparedness</div>
        </div>
        <div class="sr-twin-card__metrics">
          <div class="sr-twin-metric"><span>Flood Risk</span><strong>${f.flood_risk}%</strong></div>
          <div class="sr-twin-metric"><span>Power</span><strong>${f.power_reliability}%</strong></div>
          <div class="sr-twin-metric"><span>Medicine</span><strong>${f.medicine_stock}%</strong></div>
          <div class="sr-twin-metric"><span>Beds</span><strong>${f.bed_occupancy}%</strong></div>
          <div class="sr-twin-metric"><span>Staff</span><strong>${f.staff_availability}%</strong></div>
        </div>
      `;
      gridEl.appendChild(el);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Digital twins fetch failed", err);
  }
}

// ==================== 9. Decision Support Engine ====================

async function loadDecisionSupport() {
  const gridEl = document.getElementById("sr-decisions");
  const sitrepBtn = document.getElementById("btn-sitrep");
  if (!gridEl) return;

  try {
    const res = await fetch(`${API_BASE}/situation-room/decision-support`);
    const data = await res.json();

    gridEl.innerHTML = "";
    data.actions.forEach(act => {
      const el = document.createElement("div");
      el.className = `sr-decision-card sr-decision-card--${act.priority}`;
      el.innerHTML = `
        <div class="sr-decision-card__priority-badge">${act.priority}</div>
        <div class="sr-decision-card__content">
          <div class="sr-decision-card__action">${act.action}</div>
          <div class="sr-decision-card__meta">
            <span><i data-lucide="target"></i> ${act.estimated_impact}</span>
            <span><i data-lucide="clock"></i> ${act.timeline}</span>
          </div>
        </div>
      `;
      gridEl.appendChild(el);
    });

    // Sitrep button
    if (sitrepBtn) {
      sitrepBtn.addEventListener("click", () => {
        const sitrepEl = document.getElementById("sr-sitrep");
        if (sitrepEl.classList.contains("hidden")) {
          const sr = data.sitrep_summary;
          sitrepEl.innerHTML = `
            <div class="sr-sitrep__header">
              <h3>${sr.title}</h3>
              <div class="sr-sitrep__date">${sr.date}</div>
              <div class="sr-sitrep__risk">Overall Risk: <strong class="text-danger">${sr.overall_risk}</strong></div>
            </div>
            <div class="sr-sitrep__findings">
              <h4>Key Findings</h4>
              <ul>${sr.key_findings.map(f => `<li>${f}</li>`).join("")}</ul>
            </div>
            <div class="sr-sitrep__outlook">
              <h4>Outlook</h4>
              <p>${sr.outlook}</p>
            </div>
          `;
          sitrepEl.classList.remove("hidden");
          sitrepEl.classList.add("slide-up");
        } else {
          sitrepEl.classList.add("hidden");
        }
      });
    }

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Decision support fetch failed", err);
  }
}

// ==================== Initialize Everything ====================

document.addEventListener("DOMContentLoaded", async () => {
  await loadSituationRoom();
  await initMap();
  initTimeline();
  await updateTimeline(0);
  initAIExplain();
  initScenario();
  await loadCommunityIntel();
  startCommunityPings();
  await loadSensors();
  await loadDigitalTwins();
  await loadDecisionSupport();
});
