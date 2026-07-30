/**
 * CHEWS v3.0 — Early Warning Center (EOC) Logic
 */

// Mobile menu
const mt = document.getElementById("menu-toggle"), sb = document.getElementById("sidebar");
if (mt && sb) { mt.addEventListener("click", () => sb.classList.toggle("sidebar--open")); }

// Clock Update
function updateClock() {
  const clockEl = document.getElementById("eoc-clock");
  if (clockEl) {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString('en-GB', { timeZoneName: 'short' });
  }
}
setInterval(updateClock, 1000);
updateClock();

// Live KPI Ticker Animation
function tickKPIs() {
  const alertsVal = document.querySelector(".eoc-kpi-card:nth-child(1) .eoc-kpi-val");
  const popVal = document.querySelector(".eoc-kpi-card:nth-child(2) .eoc-kpi-val");
  
  if (alertsVal && Math.random() > 0.7) {
    let current = parseInt(alertsVal.textContent);
    let diff = Math.random() > 0.5 ? 1 : -1;
    if (current + diff > 0) {
      alertsVal.textContent = current + diff;
      alertsVal.classList.remove('kpi-animate-up', 'kpi-animate-down');
      void alertsVal.offsetWidth; // trigger reflow
      alertsVal.classList.add(diff > 0 ? 'kpi-animate-up' : 'kpi-animate-down');
    }
  }

  const slider = document.getElementById("eoc-time-slider");
  if (popVal && Math.random() > 0.7 && (!slider || slider.value == 0)) {
    let current = parseInt(popVal.textContent.replace(/,/g, ''));
    let diff = Math.floor(Math.random() * 50) * (Math.random() > 0.3 ? 1 : -1);
    if (current + diff > 0) {
      popVal.textContent = (current + diff).toLocaleString();
      popVal.classList.remove('kpi-animate-up', 'kpi-animate-down');
      void popVal.offsetWidth;
      popVal.classList.add(diff > 0 ? 'kpi-animate-up' : 'kpi-animate-down');
    }
  }
}
setInterval(tickKPIs, 3000);

// Map Initialization
let eocMap;
function initMap() {
  const mapContainer = document.getElementById("eoc-map-container");
  if (!mapContainer || !window.L) return;

  // Center on Sierra Leone
  eocMap = L.map('eoc-map-container', {
    zoomControl: false // We can add custom zoom controls if needed
  }).setView([8.460555, -11.779889], 7);

  // Use CartoDB Dark Matter for the EOC feel
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
  }).addTo(eocMap);

  // Add some mock hot zones (heatmaps or circles)
  L.circle([8.95, -12.05], {
    color: '#ef4444',
    fillColor: '#ef4444',
    fillOpacity: 0.4,
    radius: 15000
  }).addTo(eocMap).bindPopup("Level 4 Flood Risk - Bombali");

  L.circle([7.95, -11.73], {
    color: '#f97316',
    fillColor: '#f97316',
    fillOpacity: 0.4,
    radius: 20000
  }).addTo(eocMap).bindPopup("Level 3 Malaria Risk - Bo");

  // Custom Icon for alerts
  const alertIcon = L.divIcon({
    className: 'custom-div-icon',
    html: `<div style="background:#ef4444; width:16px; height:16px; border-radius:50%; box-shadow: 0 0 10px #ef4444; border: 2px solid white;"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });

  const marker = L.marker([8.95, -12.05], { icon: alertIcon }).addTo(eocMap);
  marker.on('click', () => openAiDrawer("Flood Surge Detected", "Bombali District"));

  // Simulated IoT Sensors
  const sensors = [
    { loc: [8.5, -13.2], name: "Station 14 - Freetown Coastal", status: "green", temp: 31, hum: 82, rain: 0 },
    { loc: [8.9, -12.1], name: "Station 08 - Bombali River", status: "red", temp: 29, hum: 95, rain: 120 },
    { loc: [8.0, -11.8], name: "Station 22 - Bo Central", status: "orange", temp: 34, hum: 60, rain: 0 },
    { loc: [7.8, -11.2], name: "Station 41 - Kenema East", status: "yellow", temp: 32, hum: 75, rain: 5 }
  ];

  sensors.forEach(s => {
    const color = s.status === 'red' ? '#ef4444' : s.status === 'orange' ? '#f97316' : s.status === 'yellow' ? '#facc15' : '#10b981';
    const sIcon = L.divIcon({
      className: 'custom-div-icon',
      html: `<div class="sensor-icon" style="background:${color};"></div>`,
      iconSize: [12, 12],
      iconAnchor: [6, 6]
    });
    const sm = L.marker(s.loc, { icon: sIcon }).addTo(eocMap);
    
    // Use an inline style popup for simplicity
    sm.bindPopup(`
      <div style="font-family: 'Inter', sans-serif; min-width: 150px; color: #333;">
        <strong style="display:block; border-bottom:1px solid #eee; padding-bottom:4px; margin-bottom:8px;">${s.name}</strong>
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span>Temp:</span> <strong>${s.temp}°C</strong></div>
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span>Humidity:</span> <strong>${s.hum}%</strong></div>
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span>Rainfall:</span> <strong>${s.rain}mm</strong></div>
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span>Battery:</span> <strong>98%</strong></div>
        <div style="display:flex; justify-content:space-between; color:#10b981;"><span>Signal:</span> <strong>Strong</strong></div>
        <div style="font-size:0.75rem; color:#888; margin-top:8px;">Last Sync: Just now</div>
      </div>
    `);
  });
}

// Drawer Interactions
const aiDrawer = document.getElementById("eoc-ai-drawer");
const closeDrawerBtn = document.getElementById("close-ai-drawer");

function openAiDrawer(title, location) {
  if (!aiDrawer) return;
  document.getElementById("ai-drawer-title").textContent = title;
  document.getElementById("ai-drawer-loc").innerHTML = `<i data-lucide="map-pin"></i> ${location}`;
  aiDrawer.classList.add("is-open");
  if (window.lucide) lucide.createIcons();
}

if (closeDrawerBtn) {
  closeDrawerBtn.addEventListener("click", () => {
    aiDrawer.classList.remove("is-open");
  });
}

// Mock Alert Feed
const mockAlerts = [
  { severity: 'critical', title: 'Severe Flood Surge', location: 'Bombali District', time: '2m ago', conf: '94%' },
  { severity: 'high', title: 'Malaria Outbreak Risk', location: 'Bo District', time: '14m ago', conf: '88%' },
  { severity: 'medium', title: 'Air Quality Advisory', location: 'Freetown', time: '1h ago', conf: '96%' },
  { severity: 'medium', title: 'Heatwave Warning', location: 'Kenema', time: '3h ago', conf: '82%' }
];

function renderAlertFeed() {
  const feed = document.getElementById("eoc-alert-list");
  if (!feed) return;
  
  feed.innerHTML = mockAlerts.map(a => `
    <div class="eoc-alert-item severity-${a.severity}" onclick="openAiDrawer('${a.title}', '${a.location}')">
      <div class="eoc-alert-meta">
        <span>${a.time}</span>
        <span>AI Conf: ${a.conf}</span>
      </div>
      <div class="eoc-alert-title">${a.title}</div>
      <div class="eoc-alert-loc"><i data-lucide="map-pin"></i> ${a.location}</div>
    </div>
  `).join("");
}

// Emergency Mode
const emergencyBtn = document.getElementById("btn-emergency-mode");
if (emergencyBtn) {
  emergencyBtn.addEventListener("click", () => {
    document.body.classList.toggle("eoc-emergency-mode");
    if (document.body.classList.contains("eoc-emergency-mode")) {
      emergencyBtn.innerHTML = `<i data-lucide="x-circle"></i> STAND DOWN`;
      emergencyBtn.classList.add("btn--danger");
      emergencyBtn.classList.remove("btn--sm");
      // Add red tint to map
      if (eocMap) {
        document.getElementById('eoc-map-container').style.filter = "sepia(1) hue-rotate(-50deg) saturate(3)";
      }
    } else {
      emergencyBtn.innerHTML = `<i data-lucide="alert-triangle"></i> EMERGENCY MODE`;
      emergencyBtn.classList.remove("btn--danger");
      emergencyBtn.classList.add("btn--sm");
      if (eocMap) {
        document.getElementById('eoc-map-container').style.filter = "none";
      }
    }
    if (window.lucide) lucide.createIcons();
  });
}

// Timeline Scrubber Mock Interaction
const timeline = document.getElementById("eoc-time-slider");
if (timeline) {
  timeline.addEventListener("input", (e) => {
    const val = parseInt(e.target.value);
    const kpiPop = document.querySelector(".eoc-kpi-card:nth-child(2) .eoc-kpi-val");
    if (kpiPop) {
      // Mock predictive changes
      const basePop = 142500;
      kpiPop.textContent = (basePop + (val * 15000)).toLocaleString();
    }
  });
}

// Init
document.addEventListener("DOMContentLoaded", () => {
  initMap();
  renderAlertFeed();
});
