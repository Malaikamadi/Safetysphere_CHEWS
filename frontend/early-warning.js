/**
 * CHEWS v3.0 — Early Warning Center (EOC) Logic
 * Updated: Location-specific alerts (sub-district granularity)
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

// ──────────────────────────────────────────────────────
// Location-specific data (sourced from Sierra Leone flood zone catalog)
// Each alert now pinpoints a specific community, not just a district.
// ──────────────────────────────────────────────────────

const locationData = {
  kroo_bay: {
    name: "Kroo Bay",
    district: "Western Area Urban",
    region: "Western",
    lat: 8.4892, lng: -13.2387,
    elevation: "3m",
    waterBody: "Atlantic estuary (Crocodile River outlet)",
    population: 11500,
    urbanType: "Informal Settlement",
    drainage: "Poor"
  },
  susans_bay: {
    name: "Susan's Bay",
    district: "Western Area Urban",
    region: "Western",
    lat: 8.4922, lng: -13.2333,
    elevation: "4m",
    waterBody: "Atlantic Ocean (Freetown harbour)",
    population: 13800,
    urbanType: "Informal Settlement",
    drainage: "Poor"
  },
  regent: {
    name: "Regent / Sugar Loaf",
    district: "Western Area Urban",
    region: "Western",
    lat: 8.4406, lng: -13.2336,
    elevation: "280m",
    waterBody: "Babadorie stream",
    population: 6300,
    urbanType: "Informal Settlement",
    drainage: "Moderate"
  },
  bo_town: {
    name: "Bo Town",
    district: "Bo",
    region: "Southern",
    lat: 7.9647, lng: -11.7383,
    elevation: "125m",
    waterBody: "Sewa River basin",
    population: 174354,
    urbanType: "Town",
    drainage: "Moderate"
  },
  kambia_town: {
    name: "Kambia Town",
    district: "Kambia",
    region: "Northern",
    lat: 9.1208, lng: -12.9181,
    elevation: "17m",
    waterBody: "Great Scarcies River",
    population: 17000,
    urbanType: "Town",
    drainage: "Moderate"
  },
  kenema_town: {
    name: "Kenema Town",
    district: "Kenema",
    region: "Eastern",
    lat: 7.8767, lng: -11.1903,
    elevation: "148m",
    waterBody: "Sewa-Mano basin",
    population: 200354,
    urbanType: "Town",
    drainage: "Moderate"
  },
  waterloo: {
    name: "Waterloo",
    district: "Western Area Rural",
    region: "Western",
    lat: 8.3424, lng: -13.0719,
    elevation: "24m",
    waterBody: "Ribbi / Pampana confluence",
    population: 39000,
    urbanType: "Town",
    drainage: "Moderate"
  },
  lungi_tagrin: {
    name: "Lungi / Tagrin",
    district: "Port Loko",
    region: "Northern",
    lat: 8.6044, lng: -13.1956,
    elevation: "8m",
    waterBody: "Sierra Leone River estuary",
    population: 36000,
    urbanType: "Coastal",
    drainage: "Moderate"
  },
  bonthe_island: {
    name: "Bonthe (Sherbro Island)",
    district: "Bonthe",
    region: "Southern",
    lat: 7.5269, lng: -12.5025,
    elevation: "2m",
    waterBody: "Atlantic Ocean / Sherbro estuary",
    population: 9200,
    urbanType: "Coastal",
    drainage: "Poor"
  },
  magburaka: {
    name: "Magburaka",
    district: "Tonkolili",
    region: "Northern",
    lat: 8.7203, lng: -11.9442,
    elevation: "50m",
    waterBody: "Rokel River",
    population: 25000,
    urbanType: "Town",
    drainage: "Moderate"
  },
  shenge: {
    name: "Shenge",
    district: "Moyamba",
    region: "Southern",
    lat: 8.1486, lng: -12.9533,
    elevation: "3m",
    waterBody: "Atlantic Ocean",
    population: 4900,
    urbanType: "Coastal",
    drainage: "Poor"
  }
};

// Map Initialization
let eocMap;
function initMap() {
  const mapContainer = document.getElementById("eoc-map-container");
  if (!mapContainer || !window.L) return;

  // Center on Sierra Leone
  eocMap = L.map('eoc-map-container', {
    zoomControl: false
  }).setView([8.460555, -11.779889], 7);

  // Use CartoDB Dark Matter for the EOC feel
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
  }).addTo(eocMap);

  // ── Risk zones: Location-specific circles ──
  // Critical: Kroo Bay
  L.circle([locationData.kroo_bay.lat, locationData.kroo_bay.lng], {
    color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.45, radius: 800
  }).addTo(eocMap).bindPopup(`<b>⚠ Flood Risk — Kroo Bay</b><br>Western Area Urban District<br>Pop: ${locationData.kroo_bay.population.toLocaleString()}<br>Near: ${locationData.kroo_bay.waterBody}`);

  // Critical: Susan's Bay
  L.circle([locationData.susans_bay.lat, locationData.susans_bay.lng], {
    color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.45, radius: 800
  }).addTo(eocMap).bindPopup(`<b>⚠ Flood Risk — Susan's Bay</b><br>Western Area Urban District<br>Pop: ${locationData.susans_bay.population.toLocaleString()}<br>Near: ${locationData.susans_bay.waterBody}`);

  // High: Bo Town
  L.circle([locationData.bo_town.lat, locationData.bo_town.lng], {
    color: '#f97316', fillColor: '#f97316', fillOpacity: 0.4, radius: 5000
  }).addTo(eocMap).bindPopup(`<b>⚠ Malaria Risk — Bo Town</b><br>Bo District<br>Pop: ${locationData.bo_town.population.toLocaleString()}<br>Near: ${locationData.bo_town.waterBody}`);

  // High: Kambia Town
  L.circle([locationData.kambia_town.lat, locationData.kambia_town.lng], {
    color: '#f97316', fillColor: '#f97316', fillOpacity: 0.35, radius: 4000
  }).addTo(eocMap).bindPopup(`<b>⚠ Flood Risk — Kambia Town</b><br>Kambia District<br>Pop: ${locationData.kambia_town.population.toLocaleString()}<br>Near: ${locationData.kambia_town.waterBody}`);

  // Moderate: Kenema Town
  L.circle([locationData.kenema_town.lat, locationData.kenema_town.lng], {
    color: '#facc15', fillColor: '#facc15', fillOpacity: 0.3, radius: 4000
  }).addTo(eocMap).bindPopup(`<b>Heatwave Advisory — Kenema Town</b><br>Kenema District<br>Pop: ${locationData.kenema_town.population.toLocaleString()}`);

  // Moderate: Waterloo
  L.circle([locationData.waterloo.lat, locationData.waterloo.lng], {
    color: '#facc15', fillColor: '#facc15', fillOpacity: 0.3, radius: 3000
  }).addTo(eocMap).bindPopup(`<b>Air Quality Advisory — Waterloo</b><br>Western Area Rural District<br>Pop: ${locationData.waterloo.population.toLocaleString()}`);

  // ── Clickable alert markers at specific locations ──
  const alertIcon = L.divIcon({
    className: 'custom-div-icon',
    html: `<div style="background:#ef4444; width:16px; height:16px; border-radius:50%; box-shadow: 0 0 10px #ef4444; border: 2px solid white;"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });

  const warningIcon = L.divIcon({
    className: 'custom-div-icon',
    html: `<div style="background:#f97316; width:14px; height:14px; border-radius:50%; box-shadow: 0 0 8px #f97316; border: 2px solid white;"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7]
  });

  const cautionIcon = L.divIcon({
    className: 'custom-div-icon',
    html: `<div style="background:#facc15; width:12px; height:12px; border-radius:50%; box-shadow: 0 0 6px #facc15; border: 2px solid white;"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6]
  });

  // Critical markers
  const m1 = L.marker([locationData.kroo_bay.lat, locationData.kroo_bay.lng], { icon: alertIcon }).addTo(eocMap);
  m1.on('click', () => openAiDrawer("Severe Flood Surge", "kroo_bay"));

  const m2 = L.marker([locationData.susans_bay.lat, locationData.susans_bay.lng], { icon: alertIcon }).addTo(eocMap);
  m2.on('click', () => openAiDrawer("Coastal Flood Warning", "susans_bay"));

  // High markers
  const m3 = L.marker([locationData.bo_town.lat, locationData.bo_town.lng], { icon: warningIcon }).addTo(eocMap);
  m3.on('click', () => openAiDrawer("Malaria Outbreak Risk", "bo_town"));

  const m4 = L.marker([locationData.kambia_town.lat, locationData.kambia_town.lng], { icon: warningIcon }).addTo(eocMap);
  m4.on('click', () => openAiDrawer("River Flood Warning", "kambia_town"));

  // Moderate markers
  const m5 = L.marker([locationData.kenema_town.lat, locationData.kenema_town.lng], { icon: cautionIcon }).addTo(eocMap);
  m5.on('click', () => openAiDrawer("Heatwave Warning", "kenema_town"));

  const m6 = L.marker([locationData.waterloo.lat, locationData.waterloo.lng], { icon: cautionIcon }).addTo(eocMap);
  m6.on('click', () => openAiDrawer("Air Quality Advisory", "waterloo"));

  // ── Simulated IoT Sensors ──
  const sensors = [
    { loc: [8.4892, -13.2390], name: "Sensor K01 — Kroo Bay Estuary", status: "red", temp: 29, hum: 95, rain: 120 },
    { loc: [8.4925, -13.2340], name: "Sensor S02 — Susan's Bay Harbor", status: "red", temp: 28, hum: 93, rain: 105 },
    { loc: [7.9650, -11.7390], name: "Sensor B03 — Bo Town Sewa River", status: "orange", temp: 34, hum: 60, rain: 8 },
    { loc: [9.1210, -12.9185], name: "Sensor K04 — Kambia Great Scarcies", status: "orange", temp: 30, hum: 82, rain: 45 },
    { loc: [7.8770, -11.1910], name: "Sensor KE05 — Kenema Downtown", status: "yellow", temp: 36, hum: 48, rain: 0 },
    { loc: [8.3430, -13.0725], name: "Sensor W06 — Waterloo Junction", status: "yellow", temp: 31, hum: 70, rain: 3 },
    { loc: [8.6050, -13.1960], name: "Sensor L07 — Lungi Airport", status: "green", temp: 29, hum: 78, rain: 0 },
    { loc: [8.7205, -11.9445], name: "Sensor M08 — Magburaka Bridge", status: "green", temp: 30, hum: 65, rain: 1 }
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

// Drawer Interactions — now accepts a locationId key to populate specific details
const aiDrawer = document.getElementById("eoc-ai-drawer");
const closeDrawerBtn = document.getElementById("close-ai-drawer");

function openAiDrawer(title, locationId) {
  if (!aiDrawer) return;

  const loc = locationData[locationId];
  const displayLocation = loc ? `${loc.name}, ${loc.district}` : locationId;

  document.getElementById("ai-drawer-title").textContent = title;
  document.getElementById("ai-drawer-loc").innerHTML = `<i data-lucide="map-pin"></i> ${displayLocation}`;

  // Populate location details
  const areaEl = document.getElementById("ai-drawer-area");
  const districtEl = document.getElementById("ai-drawer-district");
  const regionEl = document.getElementById("ai-drawer-region");
  const waterbodyEl = document.getElementById("ai-drawer-waterbody");
  const popEl = document.getElementById("ai-drawer-pop");
  const elevEl = document.getElementById("ai-drawer-elevation");
  const facilitiesEl = document.getElementById("ai-drawer-facilities");

  if (loc) {
    if (areaEl) areaEl.textContent = loc.name;
    if (districtEl) districtEl.textContent = loc.district + " District";
    if (regionEl) regionEl.textContent = loc.region + " Region";
    if (waterbodyEl) waterbodyEl.textContent = loc.waterBody;
    if (popEl) popEl.textContent = loc.population.toLocaleString();
    if (elevEl) elevEl.textContent = loc.elevation;
    if (facilitiesEl) {
      // Estimate facilities based on population
      const phus = Math.max(1, Math.floor(loc.population / 5000));
      facilitiesEl.textContent = phus + " PHUs";
    }
  }

  aiDrawer.classList.add("is-open");
  if (window.lucide) lucide.createIcons();
}

if (closeDrawerBtn) {
  closeDrawerBtn.addEventListener("click", () => {
    aiDrawer.classList.remove("is-open");
  });
}

// ──────────────────────────────────────────────────────
// Alert Feed — now with specific locations, not just districts
// ──────────────────────────────────────────────────────

const mockAlerts = [
  { severity: 'critical', title: 'Severe Flood Surge',       locationId: 'kroo_bay',     time: '2m ago',  conf: '97%' },
  { severity: 'critical', title: 'Coastal Flood Warning',    locationId: 'susans_bay',   time: '5m ago',  conf: '94%' },
  { severity: 'high',     title: 'Malaria Outbreak Risk',    locationId: 'bo_town',      time: '14m ago', conf: '88%' },
  { severity: 'high',     title: 'River Flood Warning',      locationId: 'kambia_town',  time: '22m ago', conf: '85%' },
  { severity: 'medium',   title: 'Heatwave Warning',         locationId: 'kenema_town',  time: '1h ago',  conf: '82%' },
  { severity: 'medium',   title: 'Air Quality Advisory',     locationId: 'waterloo',     time: '1h ago',  conf: '91%' },
  { severity: 'low',      title: 'Coastal Erosion Monitor',  locationId: 'shenge',       time: '3h ago',  conf: '78%' },
  { severity: 'low',      title: 'Dam Buffer Check',         locationId: 'magburaka',    time: '4h ago',  conf: '72%' }
];

function renderAlertFeed() {
  const feed = document.getElementById("eoc-alert-list");
  if (!feed) return;
  
  feed.innerHTML = mockAlerts.map(a => {
    const loc = locationData[a.locationId];
    const displayLoc = loc ? `${loc.name}, ${loc.district}` : a.locationId;
    
    return `
    <div class="eoc-alert-item severity-${a.severity}" onclick="openAiDrawer('${a.title}', '${a.locationId}')">
      <div class="eoc-alert-meta">
        <span>${a.time}</span>
        <span>AI Conf: ${a.conf}</span>
      </div>
      <div class="eoc-alert-title">${a.title}</div>
      <div class="eoc-alert-loc"><i data-lucide="map-pin"></i> ${displayLoc}</div>
      <div class="eoc-alert-district-tag">${loc ? loc.district + ' District · ' + loc.region + ' Region' : ''}</div>
    </div>
  `}).join("");
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
