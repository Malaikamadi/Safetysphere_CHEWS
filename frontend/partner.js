/**
 * CHEWS v4.0 — Partner Dashboard
 */

const API_BASE = "http://localhost:8000";

// ==================== Partner Map ====================
let partnerMap = null;
let partnerLayers = {};

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

  // Mock impact zones
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
    // Flood circles
    const floodCircle = L.circleMarker([z.lat, z.lng], {
      radius: 25 * (0.5 + z.flood * 0.8),
      fillColor: "#6f8faa",
      color: "transparent",
      fillOpacity: 0.4 + z.flood * 0.3,
      weight: 0,
    });
    floodCircle.bindTooltip(`<strong>${z.name}</strong><br/>Flood Risk: ${(z.flood * 100).toFixed(0)}%`, { direction: "top" });
    floodGroup.addLayer(floodCircle);

    // Malaria circles
    const malariaCircle = L.circleMarker([z.lat + 0.05, z.lng + 0.05], {
      radius: 25 * (0.5 + z.malaria * 0.8),
      fillColor: "#c75c54",
      color: "transparent",
      fillOpacity: 0.4 + z.malaria * 0.3,
      weight: 0,
    });
    malariaCircle.bindTooltip(`<strong>${z.name}</strong><br/>Malaria Risk: ${(z.malaria * 100).toFixed(0)}%`, { direction: "top" });
    malariaGroup.addLayer(malariaCircle);

    // Facility markers
    const fMarker = L.circleMarker([z.lat - 0.03, z.lng - 0.03], {
      radius: 6, fillColor: "#7d9f86", color: "#fff", fillOpacity: 0.9, weight: 2
    });
    fMarker.bindTooltip(`<strong>${z.name} Hospital</strong>`, { direction: "top" });
    facilityGroup.addLayer(fMarker);

    // Project area circles
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

  // Layer toggles
  document.querySelectorAll('input[data-layer]').forEach(cb => {
    cb.addEventListener("change", () => {
      const layer = partnerLayers[cb.dataset.layer];
      if (!layer) return;
      cb.checked ? layer.addTo(partnerMap) : partnerMap.removeLayer(layer);
    });
  });
}

// ==================== Impact Tabs ====================
function initImpactTabs() {
  document.querySelectorAll(".p-impact-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".p-impact-tab").forEach(t => t.classList.remove("p-impact-tab--active"));
      tab.classList.add("p-impact-tab--active");
    });
  });
}

// ==================== Page Init ====================
function initPartnerPage() {
  // Profile
  const roleDetails = typeof getRoleDetails !== "undefined" ? getRoleDetails() : null;
  if (roleDetails) {
    const avatarEl = document.getElementById("topbar-avatar");
    const nameEl = document.getElementById("topbar-name");
    const roleEl = document.getElementById("topbar-role-label");
    if (avatarEl) avatarEl.textContent = roleDetails.initials;
    if (nameEl) nameEl.textContent = roleDetails.fullName;
    if (roleEl) roleEl.textContent = roleDetails.subtitle;
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

  // Animate indicator fills
  setTimeout(() => {
    document.querySelectorAll(".p-indicator__fill").forEach(fill => {
      const target = fill.style.width;
      fill.style.width = "0%";
      requestAnimationFrame(() => {
        setTimeout(() => { fill.style.width = target; }, 100);
      });
    });
  }, 300);
}

document.addEventListener("DOMContentLoaded", () => {
  initPartnerPage();
  initPartnerMap();
  initImpactTabs();
});
