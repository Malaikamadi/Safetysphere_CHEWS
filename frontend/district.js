/**
 * CHEWS v4.0 — District Health Officer Dashboard
 */

const API_BASE = "/api";

// ==================== District Map ====================
let districtMap = null;
let districtLayers = {};

function initDistrictMap() {
  const mapEl = document.getElementById("district-map");
  if (!mapEl) return;

  const district = typeof getDistrict !== "undefined" ? getDistrict() : "Bombali";
  
  // District center coordinates
  const districtCoords = {
    "Western Area Urban": [8.48, -13.23],
    "Western Area Rural": [8.37, -13.18],
    "Bo": [7.96, -11.74],
    "Pujehun": [7.35, -11.72],
    "Bonthe": [7.53, -12.51],
    "Kenema": [7.87, -11.19],
    "Port Loko": [8.77, -12.79],
    "Kambia": [9.12, -12.92],
    "Tonkolili": [8.70, -11.97],
    "Moyamba": [8.16, -12.43],
    "Bombali": [9.05, -12.03],
  };

  const center = districtCoords[district] || [9.05, -12.03];
  
  districtMap = L.map("district-map", {
    center: center,
    zoom: 10,
    zoomControl: true,
    attributionControl: true,
  });

  if (window.chewsTheme && window.chewsTheme.attachBasemap) {
    window.chewsTheme.attachBasemap(districtMap);
  } else {
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      subdomains: "abc",
      maxZoom: 19,
    }).addTo(districtMap);
  }

  // Mock district risk zones
  const riskZones = [
    { lat: center[0] + 0.08, lng: center[1] - 0.05, score: 0.82, type: "flood" },
    { lat: center[0] - 0.05, lng: center[1] + 0.08, score: 0.68, type: "malaria" },
    { lat: center[0] + 0.12, lng: center[1] + 0.03, score: 0.55, type: "flood" },
    { lat: center[0] - 0.1, lng: center[1] - 0.1, score: 0.73, type: "malaria" },
  ];

  const floodGroup = L.layerGroup();
  const malariaGroup = L.layerGroup();
  const facilityGroup = L.layerGroup();

  riskZones.forEach(z => {
    const color = z.type === "flood" ? "#6f8faa" : "#c75c54";
    const group = z.type === "flood" ? floodGroup : malariaGroup;
    const circle = L.circleMarker([z.lat, z.lng], {
      radius: 25 * (0.5 + z.score * 0.8),
      fillColor: color,
      color: "transparent",
      fillOpacity: 0.45 + z.score * 0.3,
      weight: 0,
    });
    circle.bindTooltip(`<strong>${z.type === "flood" ? "Flood Risk" : "Malaria Risk"}</strong><br/>Score: ${(z.score * 100).toFixed(0)}%`, { direction: "top" });
    group.addLayer(circle);
  });

  // Mock facilities
  const facilities = [
    { name: "Makeni Government Hospital", lat: center[0] + 0.01, lng: center[1] - 0.02, ready: true },
    { name: "Kambia PHU", lat: center[0] - 0.08, lng: center[1] + 0.05, ready: true },
    { name: "Gbonko CHC", lat: center[0] + 0.06, lng: center[1] + 0.07, ready: true },
    { name: "Rogbom PHU", lat: center[0] - 0.04, lng: center[1] - 0.08, ready: false },
  ];

  facilities.forEach(f => {
    const marker = L.circleMarker([f.lat, f.lng], {
      radius: 7,
      fillColor: f.ready ? "#7d9f86" : "#c9a35c",
      color: "#fff",
      fillOpacity: 0.9,
      weight: 2,
    });
    marker.bindTooltip(`<strong>${f.name}</strong><br/>Status: ${f.ready ? "✅ Ready" : "⚠️ Partial"}`, { direction: "top" });
    facilityGroup.addLayer(marker);
  });

  districtLayers = { flood: floodGroup, malaria: malariaGroup, facilities: facilityGroup };
  floodGroup.addTo(districtMap);
  malariaGroup.addTo(districtMap);
  facilityGroup.addTo(districtMap);

  // Layer toggles
  document.querySelectorAll('input[data-layer]').forEach(cb => {
    cb.addEventListener("change", () => {
      const layer = districtLayers[cb.dataset.layer];
      if (!layer) return;
      cb.checked ? layer.addTo(districtMap) : districtMap.removeLayer(layer);
    });
  });
}

// ==================== Page Init ====================
function initDistrictPage() {
  const district = typeof getDistrict !== "undefined" ? getDistrict() : "Bombali";
  
  // Update title
  const titleEl = document.getElementById("district-title");
  if (titleEl) titleEl.textContent = `${district} District Dashboard`;

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

  // Mobile menu
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

  // Trend tabs
  document.querySelectorAll(".d-trend-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".d-trend-tab").forEach(t => t.classList.remove("d-trend-tab--active"));
      tab.classList.add("d-trend-tab--active");
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initDistrictPage();
  initDistrictMap();
});
