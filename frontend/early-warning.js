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
