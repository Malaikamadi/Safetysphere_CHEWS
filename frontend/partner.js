/**
 * CHEWS v4.0 — Partner Dashboard Sub-Pages & View Switcher
 */

const API_BASE = "/api";

let partnerMap = null;
let partnerFullMap = null;
let partnerLayers = {};

const VIEW_METADATA = {
  impact: {
    title: "Impact & Performance Dashboard",
    sub: "Tracking progress, measuring impact, supporting healthier, safer communities"
  },
  map: {
    title: "National Climate-Health Impact Map",
    sub: "Spatial risk distribution, facility vulnerability, and project area overlays"
  },
  models: {
    title: "AI Model Performance & Diagnostics",
    sub: "Evaluation metrics, confusion matrices, ROC curves, and feature importance"
  },
  mne: {
    title: "Monitoring & Evaluation (M&E) Framework",
    sub: "Quarterly impact targets, CHW compliance, and target vs actual metrics"
  },
  reports: {
    title: "Partner Policy Briefs & Reports Center",
    sub: "Download monthly impact assessments, WHO briefs, and district comparisons"
  },
  data: {
    title: "Anonymized Data & Research Hub",
    sub: "Explore open datasets, query risk indicators, and access the REST API"
  },
  forecasts: {
    title: "Climate-Health Forecasts",
    sub: "7-day multi-hazard risk predictions, rainfall outlooks, and temperature trends"
  },
  downloads: {
    title: "Data Downloads & Exports",
    sub: "Datasets, model outputs, partner reports, GIS files, and API access"
  }
};

// ==================== View Switcher ====================
function switchView(targetView) {
  const meta = VIEW_METADATA[targetView] || VIEW_METADATA.impact;

  // Update Topbar titles
  const titleEl = document.getElementById("partner-view-title");
  const subEl = document.getElementById("partner-view-sub");
  if (titleEl) titleEl.textContent = meta.title;
  if (subEl) subEl.textContent = meta.sub;

  // Update sidebar active link
  document.querySelectorAll(".sidebar__nav .nav-link").forEach(link => {
    link.classList.remove("nav-link--active");
    if (link.getAttribute("data-view") === targetView) {
      link.classList.add("nav-link--active");
    }
  });

  // Switch visible page container
  document.querySelectorAll(".p-view").forEach(v => v.classList.remove("p-view--active"));
  const viewEl = document.getElementById(`p-view-${targetView}`);
  if (viewEl) viewEl.classList.add("p-view--active");

  // Invalidate maps on view switch so Leaflet resizes correctly
  setTimeout(() => {
    if (targetView === "impact" && partnerMap) partnerMap.invalidateSize();
    if (targetView === "map") {
      if (!partnerFullMap) initPartnerFullMap();
      else partnerFullMap.invalidateSize();
    }
    if (targetView === "forecasts" && !forecastChartsDrawn) {
      drawPartnerForecastCharts();
    }
  }, 100);
}

function initViewNav() {
  document.querySelectorAll(".sidebar__nav a[data-view]").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const view = link.getAttribute("data-view");
      switchView(view);
    });
  });
}

// ==================== Main Impact Map ====================
function initPartnerMap() {
  const mapEl = document.getElementById("partner-map");
  if (!mapEl) return;

  partnerMap = L.map("partner-map", {
    center: [8.46, -11.78],
    zoom: 7,
    zoomControl: true,
    attributionControl: true,
  });

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 18,
  }).addTo(partnerMap);

  const impactZones = [
    { name: "Western Area", lat: 8.48, lng: -13.23, flood: 0.7, malaria: 0.8 },
    { name: "Bo", lat: 7.96, lng: -11.74, flood: 0.5, malaria: 0.65 },
    { name: "Kenema", lat: 7.87, lng: -11.19, flood: 0.6, malaria: 0.72 },
    { name: "Bombali", lat: 9.05, lng: -12.03, flood: 0.75, malaria: 0.55 },
    { name: "Port Loko", lat: 8.77, lng: -12.79, flood: 0.68, malaria: 0.6 },
    { name: "Moyamba", lat: 8.16, lng: -12.43, flood: 0.45, malaria: 0.5 },
  ];

  const floodGroup = L.layerGroup();
  const malariaGroup = L.layerGroup();
  const facilityGroup = L.layerGroup();
  const projectGroup = L.layerGroup();

  impactZones.forEach(z => {
    const floodCircle = L.circleMarker([z.lat, z.lng], {
      radius: 25 * (0.5 + z.flood * 0.8),
      fillColor: "#6f8faa",
      color: "transparent",
      fillOpacity: 0.4 + z.flood * 0.3,
      weight: 0,
    });
    floodCircle.bindTooltip(`<strong>${z.name}</strong><br/>Flood Risk: ${(z.flood * 100).toFixed(0)}%`, { direction: "top" });
    floodGroup.addLayer(floodCircle);

    const malariaCircle = L.circleMarker([z.lat + 0.05, z.lng + 0.05], {
      radius: 25 * (0.5 + z.malaria * 0.8),
      fillColor: "#c75c54",
      color: "transparent",
      fillOpacity: 0.4 + z.malaria * 0.3,
      weight: 0,
    });
    malariaCircle.bindTooltip(`<strong>${z.name}</strong><br/>Malaria Risk: ${(z.malaria * 100).toFixed(0)}%`, { direction: "top" });
    malariaGroup.addLayer(malariaCircle);

    const fMarker = L.circleMarker([z.lat - 0.03, z.lng - 0.03], {
      radius: 6, fillColor: "#7d9f86", color: "#fff", fillOpacity: 0.9, weight: 2
    });
    fMarker.bindTooltip(`<strong>${z.name} Hospital</strong>`, { direction: "top" });
    facilityGroup.addLayer(fMarker);

    const projCircle = L.circle([z.lat, z.lng], {
      radius: 15000,
      fillColor: "#9c7f8f",
      color: "#9c7f8f",
      fillOpacity: 0.08,
      weight: 1,
      dashArray: "4 6"
    });
    projCircle.bindTooltip(`<strong>${z.name} — Project Area</strong>`, { direction: "top" });
    projectGroup.addLayer(projCircle);
  });

  partnerLayers = { flood: floodGroup, malaria: malariaGroup, facilities: facilityGroup, projects: projectGroup };
  floodGroup.addTo(partnerMap);
  malariaGroup.addTo(partnerMap);
  facilityGroup.addTo(partnerMap);
  projectGroup.addTo(partnerMap);

  document.querySelectorAll('input[data-layer]').forEach(cb => {
    cb.addEventListener("change", () => {
      const layer = partnerLayers[cb.dataset.layer];
      if (!layer) return;
      cb.checked ? layer.addTo(partnerMap) : partnerMap.removeLayer(layer);
    });
  });
}

// ==================== Full Map View ====================
function initPartnerFullMap() {
  const mapEl = document.getElementById("partner-full-map");
  if (!mapEl) return;

  partnerFullMap = L.map("partner-full-map", {
    center: [8.46, -11.78],
    zoom: 7.5,
    zoomControl: true,
    attributionControl: true,
  });

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 18,
  }).addTo(partnerFullMap);

  const districts = [
    { name: "Koinadugu", lat: 9.5, lng: -11.4, risk: 0.82 },
    { name: "Bombali", lat: 9.05, lng: -12.03, risk: 0.76 },
    { name: "Port Loko", lat: 8.77, lng: -12.79, risk: 0.72 },
    { name: "Kenema", lat: 7.87, lng: -11.19, risk: 0.68 },
    { name: "Bo", lat: 7.96, lng: -11.74, risk: 0.65 },
    { name: "Western Area Urban", lat: 8.48, lng: -13.23, risk: 0.42 },
  ];

  districts.forEach(d => {
    const color = d.risk >= 0.75 ? "#c75c54" : d.risk >= 0.6 ? "#c9a35c" : "#7d9f86";
    const c = L.circle([d.lat, d.lng], {
      radius: 28000,
      fillColor: color,
      color: color,
      fillOpacity: 0.35,
      weight: 1.5,
    }).addTo(partnerFullMap);
    c.bindTooltip(`<strong>${d.name}</strong><br/>Risk Score: ${d.risk}`, { direction: "top" });
  });

  // Filter dropdown listener
  const filterSelect = document.getElementById("p-map-district-filter");
  if (filterSelect) {
    filterSelect.addEventListener("change", (e) => {
      const val = e.target.value;
      const target = districts.find(d => d.name === val);
      if (target) partnerFullMap.setView([target.lat, target.lng], 10);
      else partnerFullMap.setView([8.46, -11.78], 7.5);
    });
  }
}

// ==================== Data Table Filter ====================
function filterDatasetTable() {
  const query = (document.getElementById("p-data-search").value || "").toLowerCase();
  const rows = document.querySelectorAll("#p-data-tbody tr");
  rows.forEach(r => {
    const text = r.textContent.toLowerCase();
    r.style.display = text.includes(query) ? "" : "none";
  });
}

function downloadDatasetCSV() {
  alert("Downloading Sierra_Leone_Climate_Health_Dataset_2024.csv...");
}

function downloadReport(reportTitle) {
  alert(`Preparing download for "${reportTitle}"...`);
}

function exportCurrentView() {
  alert("Exporting current dashboard view summary (PDF)...");
}

// ==================== Impact Indicator Tabs ====================
function initImpactTabs() {
  const tabData = {
    health: [
      { label: "Reduction in malaria cases", type: "(year, %)", val: "24%", fill: "24%", style: "" },
      { label: "Facilities with improved readiness", type: "(target: 80%)", val: "76%", fill: "76%", style: "p-indicator__fill--accent" },
      { label: "Communities with early warning coverage", type: "", val: "68%", fill: "68%", style: "p-indicator__fill--blue" },
      { label: "CHWs submitting regular reports", type: "", val: "82%", fill: "82%", style: "p-indicator__fill--accent" },
    ],
    climate: [
      { label: "Rainfall Anomaly Detection Rate", type: "", val: "91%", fill: "91%", style: "p-indicator__fill--blue" },
      { label: "Extreme Heat Warning Coverage", type: "", val: "73%", fill: "73%", style: "" },
      { label: "Flooding Risk Forecast Accuracy", type: "", val: "85%", fill: "85%", style: "p-indicator__fill--accent" },
    ],
    sdgs: [
      { label: "SDG 3: Good Health & Well-Being", type: "(Progress)", val: "78%", fill: "78%", style: "p-indicator__fill--accent" },
      { label: "SDG 13: Climate Action", type: "(Progress)", val: "64%", fill: "64%", style: "p-indicator__fill--blue" },
    ],
    gender: [
      { label: "Pregnant Women Enrolled in Care Alerts", type: "", val: "89K", fill: "88%", style: "p-indicator__fill--accent" },
      { label: "Female CHW Workforce Proportion", type: "", val: "54%", fill: "54%", style: "p-indicator__fill--blue" },
    ]
  };

  document.querySelectorAll(".p-impact-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".p-impact-tab").forEach(t => t.classList.remove("p-impact-tab--active"));
      tab.classList.add("p-impact-tab--active");

      const key = tab.getAttribute("data-itab");
      const list = tabData[key] || tabData.health;
      const container = document.getElementById("p-indicators-container");
      if (!container) return;

      container.innerHTML = list.map(item => `
        <div class="p-indicator">
          <div class="p-indicator__info">
            <div class="p-indicator__label">${item.label} ${item.type ? `<span class="p-indicator__type">${item.type}</span>` : ""}</div>
            <div class="p-indicator__value">${item.val}</div>
          </div>
          <div class="p-indicator__bar"><div class="p-indicator__fill ${item.style}" style="width: ${item.fill}"></div></div>
        </div>
      `).join("");
    });
  });
}

// ==================== Forecast Charts ====================
let forecastChartsDrawn = false;

function drawPartnerForecastCharts() {
  drawRainfallChart();
  drawTempChart();
  forecastChartsDrawn = true;
}

function drawRainfallChart() {
  const canvas = document.getElementById("p-rainfall-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = 220 * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = '220px';
  ctx.scale(dpr, dpr);
  const W = rect.width, H = 220;
  const padL = 50, padR = 20, padT = 20, padB = 35;
  const chartW = W - padL - padR, chartH = H - padT - padB;

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const koinadugu = [168, 145, 120, 98, 85, 72, 60];
  const bombali = [142, 130, 115, 105, 88, 70, 55];
  const portLoko = [115, 100, 92, 80, 65, 55, 48];
  const maxVal = 180;

  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-1').trim() || '#0f1729';
  ctx.fillRect(0, 0, W, H);

  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (chartH / 4) * i;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + chartW, y); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.font = '11px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(maxVal - (maxVal / 4) * i) + 'mm', padL - 8, y + 4);
  }

  function drawLine(data, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    data.forEach((val, i) => {
      const x = padL + (chartW / (data.length - 1)) * i;
      const y = padT + chartH * (1 - val / maxVal);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    data.forEach((val, i) => {
      const x = padL + (chartW / (data.length - 1)) * i;
      const y = padT + chartH * (1 - val / maxVal);
      ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = color; ctx.fill();
      ctx.strokeStyle = '#0f1729'; ctx.lineWidth = 2; ctx.stroke();
    });
  }

  drawLine(koinadugu, '#ef4444');
  drawLine(bombali, '#f97316');
  drawLine(portLoko, '#facc15');

  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.font = '11px Inter, sans-serif';
  ctx.textAlign = 'center';
  days.forEach((d, i) => {
    ctx.fillText(d, padL + (chartW / (days.length - 1)) * i, H - 8);
  });

  // Legend
  [['Koinadugu','#ef4444'],['Bombali','#f97316'],['Port Loko','#facc15']].forEach(([label, color], i) => {
    const lx = padL + 10 + i * 100;
    ctx.fillStyle = color;
    ctx.fillRect(lx, padT + 2, 10, 10);
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.textAlign = 'left';
    ctx.fillText(label, lx + 14, padT + 11);
  });
}

function drawTempChart() {
  const canvas = document.getElementById("p-temp-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = 220 * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = '220px';
  ctx.scale(dpr, dpr);
  const W = rect.width, H = 220;
  const padL = 50, padR = 20, padT = 20, padB = 35;
  const chartW = W - padL - padR, chartH = H - padT - padB;

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const temp = [31, 32, 34, 33, 35, 36, 34];
  const humidity = [85, 82, 78, 80, 75, 72, 76];

  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-1').trim() || '#0f1729';
  ctx.fillRect(0, 0, W, H);

  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (chartH / 4) * i;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + chartW, y); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.font = '11px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(40 - (40 / 4) * i), padL - 8, y + 4);
  }

  // Temp line
  ctx.strokeStyle = '#f97316';
  ctx.lineWidth = 2.5;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  temp.forEach((val, i) => {
    const x = padL + (chartW / (temp.length - 1)) * i;
    const y = padT + chartH * (1 - val / 40);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  temp.forEach((val, i) => {
    const x = padL + (chartW / (temp.length - 1)) * i;
    const y = padT + chartH * (1 - val / 40);
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#f97316'; ctx.fill();
    ctx.strokeStyle = '#0f1729'; ctx.lineWidth = 2; ctx.stroke();
  });

  // Humidity bars
  const barW = chartW / days.length * 0.5;
  humidity.forEach((val, i) => {
    const x = padL + (chartW / (humidity.length - 1)) * i - barW / 2;
    const barH = chartH * (val / 100);
    const y = padT + chartH - barH;
    ctx.fillStyle = 'rgba(56,189,248,0.2)';
    ctx.fillRect(x, y, barW, barH);
  });

  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.font = '11px Inter, sans-serif';
  ctx.textAlign = 'center';
  days.forEach((d, i) => {
    ctx.fillText(d, padL + (chartW / (days.length - 1)) * i, H - 8);
  });

  // Legend
  ctx.fillStyle = '#f97316'; ctx.fillRect(padL + 10, padT + 2, 10, 10);
  ctx.fillStyle = 'rgba(255,255,255,0.5)'; ctx.textAlign = 'left';
  ctx.fillText('Temperature (°C)', padL + 24, padT + 11);
  ctx.fillStyle = 'rgba(56,189,248,0.4)'; ctx.fillRect(padL + 140, padT + 2, 10, 10);
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.fillText('Humidity (%)', padL + 154, padT + 11);
}

// ==================== Page Init ====================
function initPartnerPage() {
  const roleDetails = typeof getRoleDetails !== "undefined" ? getRoleDetails() : null;
  if (roleDetails) {
    const avatarEl = document.getElementById("topbar-avatar");
    const nameEl = document.getElementById("topbar-name");
    const roleEl = document.getElementById("topbar-role-label");
    if (avatarEl) avatarEl.textContent = roleDetails.initials;
    if (nameEl) nameEl.textContent = roleDetails.fullName;
    if (roleEl) roleEl.textContent = roleDetails.subtitle;
  }

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

  initViewNav();
}

document.addEventListener("DOMContentLoaded", () => {
  initPartnerPage();
  initPartnerMap();
  initImpactTabs();
});
