/**
 * CHEWS v3.0 — Early Warning Center
 * Three-panel UI: Alert Management, Forecast Timeline, Sensor Network
 */

// ─── Mobile menu ────────────────────────────────────────────────────
const mt = document.getElementById("menu-toggle"), sb = document.getElementById("sidebar");
if (mt && sb) { mt.addEventListener("click", () => sb.classList.toggle("sidebar--open")); }

// ─── Tab Switching ──────────────────────────────────────────────────
function ewSwitchTab(tab) {
  document.querySelectorAll(".ew-tab-content").forEach(t => t.classList.add("hidden"));
  document.querySelectorAll(".ew-tab-btn").forEach(b => {
    b.classList.remove("active-tab", "btn--secondary");
    b.classList.add("btn--ghost");
  });
  const panel = document.getElementById("ewtab-" + tab);
  if (panel) panel.classList.remove("hidden");
  const btn = document.querySelector(`[data-ewtab="${tab}"]`);
  if (btn) {
    btn.classList.add("active-tab", "btn--secondary");
    btn.classList.remove("btn--ghost");
  }
  
  const pageContainer = document.querySelector('.page');
  if (pageContainer) {
    if (tab === 'live') {
      pageContainer.classList.add('page--live-map');
      document.body.classList.add('eoc-body');
    } else {
      pageContainer.classList.remove('page--live-map');
      document.body.classList.remove('eoc-body');
    }
  }

  if (tab === 'live' && !liveMapInit) {
    setTimeout(initLiveMap, 100);
  }
  
  // Init sensor map when sensors tab is opened
  if (tab === 'sensors' && !sensorMapInit) {
    setTimeout(initSensorMap, 100);
  }
  // Draw forecast chart when forecast tab is opened
  if (tab === 'forecast' && !forecastChartDrawn) {
    setTimeout(drawForecastChart, 100);
  }
  if (window.lucide) lucide.createIcons();
}

// ═══════════════════════════════════════════════════════════════════
// TAB 1: ALERT MANAGEMENT
// ═══════════════════════════════════════════════════════════════════

const alertData = [
  { id: 'ALT-001', severity: 'critical', title: 'Severe Flood Surge', location: 'Kroo Bay', district: 'Western Area Urban', hazard: 'flood', conf: 97, status: 'active', time: '2m ago', pop: 11500, elevation: '3m', waterBody: 'Atlantic estuary', assignee: 'Capt. Sesay', actions: ['Notify DHMT', 'Preposition ORS', 'Activate CHWs'] },
  { id: 'ALT-002', severity: 'critical', title: 'Coastal Flood Warning', location: "Susan's Bay", district: 'Western Area Urban', hazard: 'flood', conf: 94, status: 'active', time: '5m ago', pop: 13800, elevation: '4m', waterBody: 'Freetown harbour', assignee: 'Lt. Koroma', actions: ['Evacuate low-lying areas', 'Deploy sandbags'] },
  { id: 'ALT-003', severity: 'critical', title: 'Mudslide Risk', location: 'Regent / Sugar Loaf', district: 'Western Area Urban', hazard: 'flood', conf: 91, status: 'monitoring', time: '12m ago', pop: 6300, elevation: '280m', waterBody: 'Babadorie stream', assignee: 'Dr. Bangura', actions: ['Restrict hilltop access', 'Monitor soil saturation'] },
  { id: 'ALT-004', severity: 'critical', title: 'Flash Flood Alert', location: 'Granville Brook', district: 'Western Area Urban', hazard: 'flood', conf: 89, status: 'active', time: '18m ago', pop: 7500, elevation: '6m', waterBody: 'Granville Brook', assignee: 'Capt. Sesay', actions: ['Clear drainage canals', 'Alert downstream communities'] },
  { id: 'ALT-005', severity: 'high', title: 'Malaria Outbreak Risk', location: 'Bo Town', district: 'Bo', hazard: 'malaria', conf: 88, status: 'active', time: '25m ago', pop: 174354, elevation: '125m', waterBody: 'Sewa River basin', assignee: 'Dr. Fofanah', actions: ['Distribute ITNs', 'Activate IRS teams'] },
  { id: 'ALT-006', severity: 'high', title: 'River Flood Warning', location: 'Kambia Town', district: 'Kambia', hazard: 'flood', conf: 85, status: 'monitoring', time: '32m ago', pop: 17000, elevation: '17m', waterBody: 'Great Scarcies River', assignee: 'Lt. Conteh', actions: ['Monitor river gauge', 'Pre-alert communities'] },
  { id: 'ALT-007', severity: 'high', title: 'Standing Water / Breeding Sites', location: 'Waterloo', district: 'Western Area Rural', hazard: 'malaria', conf: 82, status: 'active', time: '45m ago', pop: 39000, elevation: '24m', waterBody: 'Ribbi confluence', assignee: 'CHW Kamara', actions: ['Drain stagnant pools', 'Larviciding'] },
  { id: 'ALT-008', severity: 'high', title: 'Cholera Risk (Post-Flood)', location: 'Kissy / Mountain Cut', district: 'Western Area Urban', hazard: 'cholera', conf: 79, status: 'investigating', time: '1h ago', pop: 22000, elevation: '18m', waterBody: 'Aberdeen Creek', assignee: 'Dr. Bangura', actions: ['Water quality testing', 'ORS distribution'] },
  { id: 'ALT-009', severity: 'high', title: 'Coastal Erosion Alert', location: 'Bonthe Island', district: 'Bonthe', hazard: 'flood', conf: 77, status: 'monitoring', time: '1.5h ago', pop: 9200, elevation: '2m', waterBody: 'Sherbro estuary', assignee: 'Lt. Koroma', actions: ['Assess infrastructure damage'] },
  { id: 'ALT-010', severity: 'high', title: 'Tidal Surge Warning', location: 'Shenge', district: 'Moyamba', hazard: 'flood', conf: 75, status: 'active', time: '2h ago', pop: 4900, elevation: '3m', waterBody: 'Atlantic Ocean', assignee: 'CHW Sesay', actions: ['Evacuate beachfront', 'Secure fishing boats'] },
  { id: 'ALT-011', severity: 'moderate', title: 'Heatwave Warning', location: 'Kenema Town', district: 'Kenema', hazard: 'heat', conf: 82, status: 'monitoring', time: '2h ago', pop: 200354, elevation: '148m', waterBody: 'Sewa-Mano basin', assignee: 'Dr. Gbla', actions: ['Open cooling centers', 'Distribute ORS'] },
  { id: 'ALT-012', severity: 'moderate', title: 'Air Quality Advisory', location: 'Wellington', district: 'Western Area Urban', hazard: 'air', conf: 91, status: 'monitoring', time: '3h ago', pop: 27500, elevation: '12m', waterBody: 'Bunce River estuary', assignee: 'Env. Officer', actions: ['Issue public advisory'] },
  { id: 'ALT-013', severity: 'moderate', title: 'River Level Rising', location: 'Magburaka', district: 'Tonkolili', hazard: 'flood', conf: 72, status: 'monitoring', time: '3h ago', pop: 25000, elevation: '50m', waterBody: 'Rokel River', assignee: 'Lt. Conteh', actions: ['Monitor gauge hourly'] },
  { id: 'ALT-014', severity: 'moderate', title: 'Dam Buffer Zone Alert', location: 'Bumbuna', district: 'Tonkolili', hazard: 'flood', conf: 68, status: 'monitoring', time: '4h ago', pop: 4000, elevation: '110m', waterBody: 'Seli River (dam)', assignee: 'Dam Engineer', actions: ['Check spillway levels'] },
  { id: 'ALT-015', severity: 'moderate', title: 'Post-Flood Water Contamination', location: 'Calaba Town', district: 'Western Area Urban', hazard: 'cholera', conf: 65, status: 'investigating', time: '4h ago', pop: 18900, elevation: '14m', waterBody: 'Orogu River', assignee: 'Dr. Bangura', actions: ['Sample water sources'] },
  { id: 'ALT-016', severity: 'moderate', title: 'Malaria Case Cluster', location: 'Pujehun Town', district: 'Pujehun', hazard: 'malaria', conf: 71, status: 'active', time: '5h ago', pop: 8500, elevation: '28m', waterBody: 'Waanje River', assignee: 'Dr. Fofanah', actions: ['Deploy RDTs'] },
  { id: 'ALT-017', severity: 'moderate', title: 'Fever Cluster Report', location: 'Sumbuya', district: 'Bo', hazard: 'malaria', conf: 63, status: 'investigating', time: '5h ago', pop: 5400, elevation: '62m', waterBody: 'Sewa River', assignee: 'CHW Kamara', actions: ['Community investigation'] },
  { id: 'ALT-018', severity: 'moderate', title: 'Bridge Flood Risk', location: 'Mattru Jong', district: 'Bonthe', hazard: 'flood', conf: 60, status: 'monitoring', time: '6h ago', pop: 12500, elevation: '14m', waterBody: 'Jong River', assignee: 'Lt. Conteh', actions: ['Assess structural integrity'] },
];

function renderAlertTable() {
  const tbody = document.getElementById("am-alert-tbody");
  if (!tbody) return;

  const search = (document.getElementById("am-search")?.value || '').toLowerCase();
  const sevFilter = document.getElementById("am-filter-severity")?.value || 'all';
  const typeFilter = document.getElementById("am-filter-type")?.value || 'all';
  const distFilter = document.getElementById("am-filter-district")?.value || 'all';

  const filtered = alertData.filter(a => {
    if (sevFilter !== 'all' && a.severity !== sevFilter) return false;
    if (typeFilter !== 'all' && a.hazard !== typeFilter) return false;
    if (distFilter !== 'all' && a.district !== distFilter) return false;
    if (search && !a.title.toLowerCase().includes(search) && !a.location.toLowerCase().includes(search) && !a.district.toLowerCase().includes(search)) return false;
    return true;
  });

  // Update counts
  const critCount = document.getElementById("am-critical-count");
  const highCount = document.getElementById("am-high-count");
  const modCount = document.getElementById("am-mod-count");
  if (critCount) critCount.textContent = alertData.filter(a => a.severity === 'critical').length;
  if (highCount) highCount.textContent = alertData.filter(a => a.severity === 'high').length;
  if (modCount) modCount.textContent = alertData.filter(a => a.severity === 'moderate').length;

  const sevColors = { critical: '#ef4444', high: '#f97316', moderate: '#facc15', low: '#10b981' };
  const statusIcons = { active: '🔴', monitoring: '🟡', investigating: '🔵', resolved: '✅' };

  tbody.innerHTML = filtered.map(a => `
    <tr class="ew-table-row ew-table-row--${a.severity}" data-alert-id="${a.id}" onclick="showAlertDetail('${a.id}')">
      <td><span class="ew-severity-badge ew-severity--${a.severity}">${a.severity.charAt(0).toUpperCase() + a.severity.slice(1)}</span></td>
      <td>
        <div class="ew-alert-cell-title">${a.title}</div>
        <div class="ew-alert-cell-id">${a.id}</div>
      </td>
      <td><strong>${a.location}</strong></td>
      <td>${a.district}</td>
      <td><span class="ew-conf-badge">${a.conf}%</span></td>
      <td><span class="ew-status-badge ew-status--${a.status}">${statusIcons[a.status] || ''} ${a.status.charAt(0).toUpperCase() + a.status.slice(1)}</span></td>
      <td class="text-dim">${a.time}</td>
      <td>
        <button class="btn btn--ghost btn--sm ew-action-btn" onclick="event.stopPropagation(); showAlertDetail('${a.id}')" title="View details"><i data-lucide="eye"></i></button>
        <button class="btn btn--ghost btn--sm ew-action-btn" onclick="event.stopPropagation(); acknowledgeAlert('${a.id}')" title="Acknowledge"><i data-lucide="check"></i></button>
      </td>
    </tr>
  `).join("");

  if (window.lucide) lucide.createIcons();
}

function showAlertDetail(alertId) {
  const a = alertData.find(x => x.id === alertId);
  if (!a) return;
  const panel = document.getElementById("am-detail-panel");
  const title = document.getElementById("am-detail-title");
  const subtitle = document.getElementById("am-detail-subtitle");
  const body = document.getElementById("am-detail-body");

  title.textContent = a.title;
  subtitle.innerHTML = `<i data-lucide="map-pin"></i> ${a.location}, ${a.district}`;

  body.innerHTML = `
    <div class="ew-detail-section">
      <div class="ew-detail-label">AI Assessment</div>
      <div class="ew-gauge-row">
        <div class="ew-gauge-val ew-severity--${a.severity}" style="font-size:2rem;font-weight:800">${a.conf}%</div>
        <div class="ew-gauge-bar"><div class="ew-gauge-fill" style="width:${a.conf}%;background:${a.severity === 'critical' ? '#ef4444' : a.severity === 'high' ? '#f97316' : '#facc15'}"></div></div>
        <div class="ew-gauge-meta">Confidence · ${a.severity.toUpperCase()}</div>
      </div>
    </div>

    <div class="ew-detail-section">
      <div class="ew-detail-label"><i data-lucide="map-pin"></i> Location Details</div>
      <div class="ew-detail-grid">
        <div><span class="text-dim">Area</span><strong>${a.location}</strong></div>
        <div><span class="text-dim">District</span><strong>${a.district}</strong></div>
        <div><span class="text-dim">Population</span><strong>${a.pop.toLocaleString()}</strong></div>
        <div><span class="text-dim">Elevation</span><strong>${a.elevation}</strong></div>
        <div><span class="text-dim">Water Body</span><strong class="text-blue">${a.waterBody}</strong></div>
        <div><span class="text-dim">Assigned</span><strong>${a.assignee}</strong></div>
      </div>
    </div>

    <div class="ew-detail-section">
      <div class="ew-detail-label"><i data-lucide="activity"></i> Status Timeline</div>
      <div class="ew-timeline">
        <div class="ew-timeline-item ew-timeline--current">
          <div class="ew-timeline-dot"></div>
          <div><strong>${a.status.charAt(0).toUpperCase() + a.status.slice(1)}</strong> <span class="text-dim">${a.time}</span></div>
        </div>
        <div class="ew-timeline-item">
          <div class="ew-timeline-dot"></div>
          <div>AI Detection triggered <span class="text-dim">auto</span></div>
        </div>
        <div class="ew-timeline-item">
          <div class="ew-timeline-dot"></div>
          <div>Sensor threshold exceeded <span class="text-dim">sensor</span></div>
        </div>
      </div>
    </div>

    <div class="ew-detail-section">
      <div class="ew-detail-label"><i data-lucide="check-square"></i> Recommended Actions</div>
      <ul class="ew-action-list">
        ${a.actions.map(act => `<li><label><input type="checkbox"> <span>${act}</span></label></li>`).join('')}
      </ul>
    </div>

    <div class="ew-detail-actions">
      <button class="btn btn--primary btn--full"><i data-lucide="zap"></i> Execute Selected Actions</button>
      <button class="btn btn--ghost btn--full" style="margin-top:0.5rem" onclick="acknowledgeAlert('${a.id}')"><i data-lucide="check-circle"></i> Acknowledge Alert</button>
    </div>
  `;

  panel.classList.add("is-open");
  if (window.lucide) lucide.createIcons();
}

function acknowledgeAlert(id) {
  const a = alertData.find(x => x.id === id);
  if (a) {
    a.status = 'resolved';
    renderAlertTable();
  }
}

// ═══════════════════════════════════════════════════════════════════
// TAB 2: FORECAST TIMELINE (Canvas Chart)
// ═══════════════════════════════════════════════════════════════════

let forecastChartDrawn = false;

function drawForecastChart() {
  const canvas = document.getElementById("fc-timeline-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // High-DPI canvas
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = 280 * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = '280px';
  ctx.scale(dpr, dpr);

  const W = rect.width, H = 280;
  const padL = 50, padR = 30, padT = 20, padB = 40;
  const chartW = W - padL - padR, chartH = H - padT - padB;

  // Data — 7 days × 4 hazards
  const days = ['Thu', 'Fri', 'Sat', 'Sun', 'Mon', 'Tue', 'Wed'];
  const flood   = [87, 92, 78, 60, 45, 30, 22];
  const malaria = [72, 74, 75, 78, 76, 70, 65];
  const heat    = [54, 68, 62, 48, 42, 38, 40];
  const air     = [42, 38, 35, 30, 28, 25, 22];

  const colors = { flood: '#ef4444', malaria: '#a855f7', heat: '#f97316', air: '#38bdf8' };

  // Background
  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-1').trim() || '#0f1729';
  ctx.fillRect(0, 0, W, H);

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (chartH / 4) * i;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + chartW, y); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.font = '11px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText((100 - 25 * i) + '%', padL - 8, y + 4);
  }

  // Danger zones
  ctx.fillStyle = 'rgba(239,68,68,0.06)';
  ctx.fillRect(padL, padT, chartW, chartH * 0.2); // > 80% = critical
  ctx.fillStyle = 'rgba(249,115,22,0.04)';
  ctx.fillRect(padL, padT + chartH * 0.2, chartW, chartH * 0.2); // 60-80% = high

  // Draw lines
  function drawLine(data, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    data.forEach((val, i) => {
      const x = padL + (chartW / (data.length - 1)) * i;
      const y = padT + chartH * (1 - val / 100);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Gradient fill under line
    ctx.globalAlpha = 0.08;
    ctx.lineTo(padL + chartW, padT + chartH);
    ctx.lineTo(padL, padT + chartH);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.globalAlpha = 1;

    // Dots
    data.forEach((val, i) => {
      const x = padL + (chartW / (data.length - 1)) * i;
      const y = padT + chartH * (1 - val / 100);
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#0f1729';
      ctx.lineWidth = 2;
      ctx.stroke();
    });
  }

  drawLine(flood, colors.flood);
  drawLine(malaria, colors.malaria);
  drawLine(heat, colors.heat);
  drawLine(air, colors.air);

  // X-axis labels
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.font = '12px Inter, sans-serif';
  ctx.textAlign = 'center';
  days.forEach((d, i) => {
    const x = padL + (chartW / (days.length - 1)) * i;
    ctx.fillText(d, x, H - 10);
  });

  // Today marker
  ctx.strokeStyle = 'rgba(255,255,255,0.3)';
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padL, padT);
  ctx.lineTo(padL, padT + chartH);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#10b981';
  ctx.font = 'bold 10px Inter, sans-serif';
  ctx.fillText('TODAY', padL, padT - 6);

  forecastChartDrawn = true;
}

// ═══════════════════════════════════════════════════════════════════
// TAB 3: SENSOR NETWORK
// ═══════════════════════════════════════════════════════════════════

let sensorMapInit = false;
let sensorMap;

const sensorData = [
  { id: 'SN-K01', name: 'Kroo Bay Estuary', location: 'Kroo Bay', district: 'W. Area Urban', lat: 8.4892, lng: -13.2387, status: 'online', temp: 29, humidity: 95, rain: 120, battery: 92, signal: 'Strong', lastSync: '30s ago', alert: true },
  { id: 'SN-S02', name: "Susan's Bay Harbor", location: "Susan's Bay", district: 'W. Area Urban', lat: 8.4922, lng: -13.2333, status: 'online', temp: 28, humidity: 93, rain: 105, battery: 88, signal: 'Strong', lastSync: '45s ago', alert: true },
  { id: 'SN-R03', name: 'Regent Hill Station', location: 'Regent', district: 'W. Area Urban', lat: 8.4406, lng: -13.2336, status: 'online', temp: 26, humidity: 88, rain: 85, battery: 95, signal: 'Strong', lastSync: '1m ago', alert: false },
  { id: 'SN-B04', name: 'Bo Town Sewa River', location: 'Bo Town', district: 'Bo', lat: 7.9647, lng: -11.7383, status: 'online', temp: 34, humidity: 60, rain: 8, battery: 76, signal: 'Good', lastSync: '2m ago', alert: false },
  { id: 'SN-K05', name: 'Kambia Great Scarcies', location: 'Kambia Town', district: 'Kambia', lat: 9.1208, lng: -12.9181, status: 'warning', temp: 30, humidity: 82, rain: 45, battery: 28, signal: 'Weak', lastSync: '5m ago', alert: true },
  { id: 'SN-KE06', name: 'Kenema Downtown', location: 'Kenema Town', district: 'Kenema', lat: 7.8767, lng: -11.1903, status: 'online', temp: 36, humidity: 48, rain: 0, battery: 91, signal: 'Strong', lastSync: '1m ago', alert: false },
  { id: 'SN-W07', name: 'Waterloo Junction', location: 'Waterloo', district: 'W. Area Rural', lat: 8.3424, lng: -13.0719, status: 'online', temp: 31, humidity: 70, rain: 3, battery: 84, signal: 'Good', lastSync: '2m ago', alert: false },
  { id: 'SN-L08', name: 'Lungi Airport', location: 'Lungi', district: 'Port Loko', lat: 8.6044, lng: -13.1956, status: 'online', temp: 29, humidity: 78, rain: 0, battery: 97, signal: 'Strong', lastSync: '30s ago', alert: false },
  { id: 'SN-M09', name: 'Magburaka Bridge', location: 'Magburaka', district: 'Tonkolili', lat: 8.7203, lng: -11.9442, status: 'online', temp: 30, humidity: 65, rain: 1, battery: 89, signal: 'Good', lastSync: '1m ago', alert: false },
  { id: 'SN-BU10', name: 'Bumbuna Dam', location: 'Bumbuna', district: 'Tonkolili', lat: 9.0292, lng: -11.7414, status: 'online', temp: 27, humidity: 72, rain: 12, battery: 93, signal: 'Strong', lastSync: '30s ago', alert: false },
  { id: 'SN-P11', name: 'Pujehun Waanje River', location: 'Pujehun', district: 'Pujehun', lat: 7.3500, lng: -11.7164, status: 'warning', temp: 32, humidity: 80, rain: 35, battery: 22, signal: 'Weak', lastSync: '8m ago', alert: true },
  { id: 'SN-SH12', name: 'Shenge Coastal', location: 'Shenge', district: 'Moyamba', lat: 8.1486, lng: -12.9533, status: 'offline', temp: null, humidity: null, rain: null, battery: 5, signal: 'None', lastSync: '3h ago', alert: false },
  { id: 'SN-BT13', name: 'Bonthe Island Wharf', location: 'Bonthe', district: 'Bonthe', lat: 7.5269, lng: -12.5025, status: 'offline', temp: null, humidity: null, rain: null, battery: 0, signal: 'None', lastSync: '12h ago', alert: false },
  { id: 'SN-WE14', name: 'Wellington Industrial', location: 'Wellington', district: 'W. Area Urban', lat: 8.4717, lng: -13.1634, status: 'online', temp: 30, humidity: 74, rain: 15, battery: 81, signal: 'Good', lastSync: '1m ago', alert: false },
  { id: 'SN-GB15', name: 'Granville Brook Canal', location: 'Kingtom', district: 'W. Area Urban', lat: 8.4845, lng: -13.2475, status: 'online', temp: 29, humidity: 90, rain: 92, battery: 86, signal: 'Strong', lastSync: '30s ago', alert: true },
  { id: 'SN-HJ16', name: 'Hastings Highway', location: 'Hastings', district: 'W. Area Rural', lat: 8.4076, lng: -13.1114, status: 'online', temp: 30, humidity: 72, rain: 5, battery: 90, signal: 'Good', lastSync: '2m ago', alert: false },
  { id: 'SN-CL17', name: 'Calaba Town Orogu', location: 'Calaba Town', district: 'W. Area Urban', lat: 8.4633, lng: -13.1490, status: 'warning', temp: 31, humidity: 78, rain: 28, battery: 35, signal: 'Weak', lastSync: '6m ago', alert: false },
  { id: 'SN-RK18', name: 'Rokupr Rice Station', location: 'Rokupr', district: 'Kambia', lat: 8.6817, lng: -12.3825, status: 'offline', temp: null, humidity: null, rain: null, battery: 2, signal: 'None', lastSync: '18h ago', alert: false },
  { id: 'SN-LM19', name: 'Lumley Beach', location: 'Lumley', district: 'W. Area Urban', lat: 8.4670, lng: -13.2853, status: 'online', temp: 28, humidity: 82, rain: 10, battery: 94, signal: 'Strong', lastSync: '1m ago', alert: false },
  { id: 'SN-MJ20', name: 'Mattru Jong Bridge', location: 'Mattru Jong', district: 'Bonthe', lat: 7.6242, lng: -11.9433, status: 'online', temp: 31, humidity: 76, rain: 18, battery: 79, signal: 'Good', lastSync: '3m ago', alert: false },
  { id: 'SN-SM21', name: 'Sumbuya Sewa River', location: 'Sumbuya', district: 'Bo', lat: 7.6547, lng: -11.9000, status: 'online', temp: 33, humidity: 68, rain: 4, battery: 82, signal: 'Good', lastSync: '2m ago', alert: false },
  { id: 'SN-KS22', name: 'Kissy Flood Gauge', location: 'Kissy', district: 'W. Area Urban', lat: 8.4810, lng: -13.1862, status: 'offline', temp: null, humidity: null, rain: null, battery: 8, signal: 'None', lastSync: '6h ago', alert: false },
  { id: 'SN-MB23', name: 'Mabella Harbour', location: 'Mabella', district: 'W. Area Urban', lat: 8.4945, lng: -13.2214, status: 'online', temp: 29, humidity: 91, rain: 88, battery: 87, signal: 'Strong', lastSync: '30s ago', alert: true },
];

function renderSensorTable() {
  const tbody = document.getElementById("sn-table-body");
  if (!tbody) return;

  const search = (document.getElementById("sn-search")?.value || '').toLowerCase();
  const statusFilter = document.getElementById("sn-filter-status")?.value || 'all';

  const filtered = sensorData.filter(s => {
    if (statusFilter !== 'all' && s.status !== statusFilter) return false;
    if (search && !s.name.toLowerCase().includes(search) && !s.location.toLowerCase().includes(search) && !s.id.toLowerCase().includes(search)) return false;
    return true;
  });

  const statusColors = { online: '#10b981', warning: '#facc15', offline: '#ef4444' };
  const statusDots = { online: '🟢', warning: '🟡', offline: '🔴' };

  tbody.innerHTML = filtered.map(s => `
    <tr class="ew-table-row" data-sensor="${s.id}" onclick="showSensorDetail('${s.id}')">
      <td><span class="ew-status-dot" style="background:${statusColors[s.status]}">${statusDots[s.status]}</span></td>
      <td>
        <div class="ew-alert-cell-title">${s.name}</div>
        <div class="ew-alert-cell-id">${s.id}</div>
      </td>
      <td>${s.location}, ${s.district}</td>
      <td>${s.temp !== null ? s.temp + '°C' : '—'}</td>
      <td>${s.humidity !== null ? s.humidity + '%' : '—'}</td>
      <td>${s.rain !== null ? s.rain + 'mm' : '—'}</td>
      <td><span class="ew-battery ${s.battery < 20 ? 'ew-battery--low' : s.battery < 50 ? 'ew-battery--mid' : ''}">${s.battery}%</span></td>
      <td class="text-dim">${s.lastSync}</td>
    </tr>
  `).join("");

  if (window.lucide) lucide.createIcons();
}

function showSensorDetail(sensorId) {
  const s = sensorData.find(x => x.id === sensorId);
  if (!s) return;
  const panel = document.getElementById("sn-detail-panel");
  const title = document.getElementById("sn-detail-title");
  const subtitle = document.getElementById("sn-detail-subtitle");
  const body = document.getElementById("sn-detail-body");

  title.textContent = s.name;
  subtitle.textContent = `${s.id} · ${s.location}, ${s.district}`;

  const statusColors = { online: '#10b981', warning: '#facc15', offline: '#ef4444' };

  body.innerHTML = `
    <div class="ew-detail-section">
      <div class="ew-detail-label">Sensor Status</div>
      <div class="ew-sensor-status-card" style="border-left: 4px solid ${statusColors[s.status]}">
        <div class="ew-detail-grid">
          <div><span class="text-dim">Status</span><strong style="color:${statusColors[s.status]}">${s.status.toUpperCase()}</strong></div>
          <div><span class="text-dim">Signal</span><strong>${s.signal}</strong></div>
          <div><span class="text-dim">Battery</span><strong class="${s.battery < 20 ? 'text-red' : ''}">${s.battery}%</strong></div>
          <div><span class="text-dim">Last Sync</span><strong>${s.lastSync}</strong></div>
        </div>
      </div>
    </div>

    ${s.status !== 'offline' ? `
    <div class="ew-detail-section">
      <div class="ew-detail-label"><i data-lucide="activity"></i> Live Readings</div>
      <div class="ew-reading-cards">
        <div class="ew-reading-card">
          <div class="ew-reading-card__icon"><i data-lucide="thermometer"></i></div>
          <div class="ew-reading-card__val">${s.temp}°C</div>
          <div class="ew-reading-card__label">Temperature</div>
        </div>
        <div class="ew-reading-card">
          <div class="ew-reading-card__icon"><i data-lucide="droplets"></i></div>
          <div class="ew-reading-card__val">${s.humidity}%</div>
          <div class="ew-reading-card__label">Humidity</div>
        </div>
        <div class="ew-reading-card">
          <div class="ew-reading-card__icon"><i data-lucide="cloud-rain"></i></div>
          <div class="ew-reading-card__val">${s.rain}mm</div>
          <div class="ew-reading-card__label">Rainfall</div>
        </div>
      </div>
    </div>
    ` : `
    <div class="ew-detail-section">
      <div class="ew-offline-notice">
        <i data-lucide="wifi-off"></i>
        <div>
          <strong>Sensor Offline</strong>
          <p>Last seen ${s.lastSync}. ${s.battery < 10 ? 'Battery critically low — replace unit.' : 'Check connectivity.'}</p>
        </div>
      </div>
    </div>
    `}

    <div class="ew-detail-section">
      <div class="ew-detail-label"><i data-lucide="map-pin"></i> Location</div>
      <div class="ew-detail-grid">
        <div><span class="text-dim">Coordinates</span><strong>${s.lat.toFixed(4)}, ${s.lng.toFixed(4)}</strong></div>
        <div><span class="text-dim">Area</span><strong>${s.location}</strong></div>
        <div><span class="text-dim">District</span><strong>${s.district}</strong></div>
        <div><span class="text-dim">Alert Trigger</span><strong class="${s.alert ? 'text-red' : 'text-green'}">${s.alert ? 'YES — Thresholds exceeded' : 'No'}</strong></div>
      </div>
    </div>

    <div class="ew-detail-actions">
      ${s.status === 'offline' ? '<button class="btn btn--primary btn--full"><i data-lucide="refresh-cw"></i> Request Remote Reset</button>' : '<button class="btn btn--ghost btn--full"><i data-lucide="download"></i> Download Data (CSV)</button>'}
    </div>
  `;

  panel.classList.add("is-open");
  if (window.lucide) lucide.createIcons();
}

function initSensorMap() {
  const container = document.getElementById("sn-map-container");
  if (!container || !window.L || sensorMapInit) return;

  sensorMap = L.map('sn-map-container', { zoomControl: true }).setView([8.460555, -11.779889], 7);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OSM &copy; CARTO',
    subdomains: 'abcd', maxZoom: 18
  }).addTo(sensorMap);

  const statusColors = { online: '#10b981', warning: '#facc15', offline: '#ef4444' };

  sensorData.forEach(s => {
    const color = statusColors[s.status];
    const icon = L.divIcon({
      className: 'custom-div-icon',
      html: `<div style="background:${color};width:${s.alert ? 16 : 12}px;height:${s.alert ? 16 : 12}px;border-radius:50%;box-shadow:0 0 ${s.alert ? 12 : 6}px ${color};border:2px solid white;${s.alert ? 'animation:pulse 1.5s infinite' : ''}"></div>`,
      iconSize: [s.alert ? 16 : 12, s.alert ? 16 : 12],
      iconAnchor: [s.alert ? 8 : 6, s.alert ? 8 : 6]
    });

    const marker = L.marker([s.lat, s.lng], { icon }).addTo(sensorMap);
    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:160px;color:#333;">
        <strong style="display:block;border-bottom:1px solid #eee;padding-bottom:4px;margin-bottom:6px">${s.name}</strong>
        <div style="display:flex;justify-content:space-between;margin-bottom:3px"><span>Status:</span><strong style="color:${color}">${s.status.toUpperCase()}</strong></div>
        ${s.temp !== null ? `<div style="display:flex;justify-content:space-between;margin-bottom:3px"><span>Temp:</span><strong>${s.temp}°C</strong></div>` : ''}
        ${s.humidity !== null ? `<div style="display:flex;justify-content:space-between;margin-bottom:3px"><span>Humidity:</span><strong>${s.humidity}%</strong></div>` : ''}
        ${s.rain !== null ? `<div style="display:flex;justify-content:space-between;margin-bottom:3px"><span>Rain:</span><strong>${s.rain}mm</strong></div>` : ''}
        <div style="display:flex;justify-content:space-between;margin-bottom:3px"><span>Battery:</span><strong>${s.battery}%</strong></div>
        <div style="font-size:0.75rem;color:#888;margin-top:6px">Last sync: ${s.lastSync}</div>
      </div>
    `);
    marker.on('click', () => showSensorDetail(s.id));
  });

  sensorMapInit = true;
}

// ─── Close panels ───────────────────────────────────────────────────
document.getElementById("am-detail-close")?.addEventListener("click", () => {
  document.getElementById("am-detail-panel")?.classList.remove("is-open");
});
document.getElementById("sn-detail-close")?.addEventListener("click", () => {
  document.getElementById("sn-detail-panel")?.classList.remove("is-open");
});

// ─── Filter listeners ──────────────────────────────────────────────
['am-search', 'am-filter-severity', 'am-filter-type', 'am-filter-district'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener(el.type === 'text' ? 'input' : 'change', renderAlertTable);
});
['sn-search', 'sn-filter-status'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener(el.type === 'text' ? 'input' : 'change', renderSensorTable);
});

// ═══════════════════════════════════════════════════════════════════
// TAB 0: LIVE MAP
// ═══════════════════════════════════════════════════════════════════

const locationData = {
  kroo_bay: {
    name: "Kroo Bay", district: "Western Area Urban", region: "Western", lat: 8.4892, lng: -13.2387,
    elevation: "3m", waterBody: "Atlantic estuary (Crocodile River outlet)", population: 11500,
  },
  susans_bay: {
    name: "Susan's Bay", district: "Western Area Urban", region: "Western", lat: 8.4922, lng: -13.2333,
    elevation: "4m", waterBody: "Atlantic Ocean (Freetown harbour)", population: 13800,
  },
  bo_town: {
    name: "Bo Town", district: "Bo", region: "Southern", lat: 7.9647, lng: -11.7383,
    elevation: "125m", waterBody: "Sewa River basin", population: 174354,
  },
  kambia_town: {
    name: "Kambia Town", district: "Kambia", region: "Northern", lat: 9.1208, lng: -12.9181,
    elevation: "17m", waterBody: "Great Scarcies River", population: 17000,
  },
  kenema_town: {
    name: "Kenema Town", district: "Kenema", region: "Eastern", lat: 7.8767, lng: -11.1903,
    elevation: "148m", waterBody: "Sewa-Mano basin", population: 200354,
  },
  waterloo: {
    name: "Waterloo", district: "Western Area Rural", region: "Western", lat: 8.3424, lng: -13.0719,
    elevation: "24m", waterBody: "Ribbi / Pampana confluence", population: 39000,
  }
};

let liveMapInit = false;
let eocMap;
function initLiveMap() {
  const mapContainer = document.getElementById("eoc-map-container");
  if (!mapContainer || !window.L || liveMapInit) return;

  eocMap = L.map('eoc-map-container', { zoomControl: false }).setView([8.460555, -11.779889], 7);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OSM contributors &copy; CARTO',
    subdomains: 'abcd', maxZoom: 20
  }).addTo(eocMap);

  L.circle([locationData.kroo_bay.lat, locationData.kroo_bay.lng], { color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.45, radius: 800 }).addTo(eocMap);
  L.circle([locationData.susans_bay.lat, locationData.susans_bay.lng], { color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.45, radius: 800 }).addTo(eocMap);
  L.circle([locationData.bo_town.lat, locationData.bo_town.lng], { color: '#f97316', fillColor: '#f97316', fillOpacity: 0.4, radius: 5000 }).addTo(eocMap);
  L.circle([locationData.kambia_town.lat, locationData.kambia_town.lng], { color: '#f97316', fillColor: '#f97316', fillOpacity: 0.35, radius: 4000 }).addTo(eocMap);
  L.circle([locationData.kenema_town.lat, locationData.kenema_town.lng], { color: '#facc15', fillColor: '#facc15', fillOpacity: 0.3, radius: 4000 }).addTo(eocMap);
  L.circle([locationData.waterloo.lat, locationData.waterloo.lng], { color: '#facc15', fillColor: '#facc15', fillOpacity: 0.3, radius: 3000 }).addTo(eocMap);

  const alertIcon = L.divIcon({ className: 'custom-div-icon', html: `<div style="background:#ef4444; width:16px; height:16px; border-radius:50%; box-shadow: 0 0 10px #ef4444; border: 2px solid white;"></div>`, iconSize: [16, 16], iconAnchor: [8, 8] });
  const warningIcon = L.divIcon({ className: 'custom-div-icon', html: `<div style="background:#f97316; width:14px; height:14px; border-radius:50%; box-shadow: 0 0 8px #f97316; border: 2px solid white;"></div>`, iconSize: [14, 14], iconAnchor: [7, 7] });
  const cautionIcon = L.divIcon({ className: 'custom-div-icon', html: `<div style="background:#facc15; width:12px; height:12px; border-radius:50%; box-shadow: 0 0 6px #facc15; border: 2px solid white;"></div>`, iconSize: [12, 12], iconAnchor: [6, 6] });

  L.marker([locationData.kroo_bay.lat, locationData.kroo_bay.lng], { icon: alertIcon }).addTo(eocMap).on('click', () => openAiDrawer("Severe Flood Surge", "kroo_bay"));
  L.marker([locationData.susans_bay.lat, locationData.susans_bay.lng], { icon: alertIcon }).addTo(eocMap).on('click', () => openAiDrawer("Coastal Flood Warning", "susans_bay"));
  L.marker([locationData.bo_town.lat, locationData.bo_town.lng], { icon: warningIcon }).addTo(eocMap).on('click', () => openAiDrawer("Malaria Outbreak Risk", "bo_town"));
  L.marker([locationData.kambia_town.lat, locationData.kambia_town.lng], { icon: warningIcon }).addTo(eocMap).on('click', () => openAiDrawer("River Flood Warning", "kambia_town"));
  L.marker([locationData.kenema_town.lat, locationData.kenema_town.lng], { icon: cautionIcon }).addTo(eocMap).on('click', () => openAiDrawer("Heatwave Warning", "kenema_town"));
  L.marker([locationData.waterloo.lat, locationData.waterloo.lng], { icon: cautionIcon }).addTo(eocMap).on('click', () => openAiDrawer("Air Quality Advisory", "waterloo"));

  liveMapInit = true;
}

const aiDrawer = document.getElementById("eoc-ai-drawer");
const closeDrawerBtn = document.getElementById("close-ai-drawer");

function openAiDrawer(title, locationId) {
  if (!aiDrawer) return;
  const loc = locationData[locationId];
  const displayLocation = loc ? `${loc.name}, ${loc.district}` : locationId;
  document.getElementById("ai-drawer-title").textContent = title;
  document.getElementById("ai-drawer-loc").innerHTML = `<i data-lucide="map-pin"></i> ${displayLocation}`;
  
  if (loc) {
    const elId = id => document.getElementById(id);
    if(elId("ai-drawer-area")) elId("ai-drawer-area").textContent = loc.name;
    if(elId("ai-drawer-district")) elId("ai-drawer-district").textContent = loc.district + " District";
    if(elId("ai-drawer-region")) elId("ai-drawer-region").textContent = loc.region + " Region";
    if(elId("ai-drawer-waterbody")) elId("ai-drawer-waterbody").textContent = loc.waterBody;
    if(elId("ai-drawer-pop")) elId("ai-drawer-pop").textContent = loc.population.toLocaleString();
    if(elId("ai-drawer-elevation")) elId("ai-drawer-elevation").textContent = loc.elevation;
    if(elId("ai-drawer-facilities")) elId("ai-drawer-facilities").textContent = Math.max(1, Math.floor(loc.population / 5000)) + " PHUs";
  }
  
  aiDrawer.classList.add("is-open");
  if (window.lucide) lucide.createIcons();
}

if (closeDrawerBtn) {
  closeDrawerBtn.addEventListener("click", () => aiDrawer.classList.remove("is-open"));
}

const mockAlerts = [
  { severity: 'critical', title: 'Severe Flood Surge',       locationId: 'kroo_bay',     time: '2m ago',  conf: '97%' },
  { severity: 'critical', title: 'Coastal Flood Warning',    locationId: 'susans_bay',   time: '5m ago',  conf: '94%' },
  { severity: 'high',     title: 'Malaria Outbreak Risk',    locationId: 'bo_town',      time: '14m ago', conf: '88%' },
  { severity: 'high',     title: 'River Flood Warning',      locationId: 'kambia_town',  time: '22m ago', conf: '85%' },
];

function renderAlertFeed() {
  const feed = document.getElementById("eoc-alert-list");
  if (!feed) return;
  feed.innerHTML = mockAlerts.map(a => {
    const loc = locationData[a.locationId];
    const displayLoc = loc ? `${loc.name}, ${loc.district}` : a.locationId;
    return `
    <div class="eoc-alert-item severity-${a.severity}" onclick="openAiDrawer('${a.title}', '${a.locationId}')">
      <div class="eoc-alert-meta"><span>${a.time}</span><span>AI Conf: ${a.conf}</span></div>
      <div class="eoc-alert-title">${a.title}</div>
      <div class="eoc-alert-loc"><i data-lucide="map-pin"></i> ${displayLoc}</div>
    </div>`;
  }).join("");
}

// ─── Init ───────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  renderAlertTable();
  renderSensorTable();
  renderAlertFeed();
  ewSwitchTab('live');
});
