/**
 * CHEWS 4.0 — Role Management
 * Handles role-based access control, login, and sidebar generation.
 */

const ROLE_KEY = 'chews-role';
const DISTRICT_KEY = 'chews-district';

const ROLE_PERMISSIONS = {
  'admin': {
    name: 'National Administrator',
    page: 'index.html'
  },
  'district': {
    name: 'District Health Officer',
    page: 'district.html'
  },
  'worker': {
    name: 'Health Worker',
    page: 'chw.html'
  },
  'partner': {
    name: 'Partner',
    page: 'partner.html'
  }
};

const SIDEBAR_CONFIG = {
  admin: [
    { label: 'Command Center', icon: 'crosshair', url: 'index.html' },
    { label: 'Strategic Planning', icon: 'map', subnav: [
      { label: 'Risk & Hazard Maps', url: 'strategic.html#atlas' },
      { label: 'Vulnerability Assessment', url: 'strategic.html#vulnerability' },
      { label: 'Analysis & Trends', url: 'strategic.html#trends' },
      { label: 'Alerts & Reports', url: 'strategic.html#alerts' }
    ]},
    { label: 'Early Warning', icon: 'zap', subnav: [
      { label: 'Live Operations', url: 'early-warning.html' },
      { label: 'Alert Management', url: 'early-warning.html#alerts' },
      { label: 'Forecast Timeline', url: 'early-warning.html#forecast' },
      { label: 'Sensor Network', url: 'early-warning.html#sensors' }
    ]},
    { label: 'Healthcare Readiness', icon: 'hospital', subnav: [
      { label: 'Disease Forecast', url: 'healthcare.html#forecast' },
      { label: 'Facility Readiness', url: 'healthcare.html#readiness' },
      { label: 'Surge Planning', url: 'healthcare.html#surge' }
    ]},
    { label: 'Community Intelligence', icon: 'users', subnav: [
      { label: 'CHW Reports', url: 'index.html#chw' },
      { label: 'Verification Queue', url: 'index.html#queue' },
      { label: 'Community Alerts', url: 'index.html#community-alerts' }
    ]},
    { label: 'Reports & Analytics', icon: 'bar-chart-2', subnav: [
      { label: 'Situation Reports', url: 'index.html#reports-sitrep' },
      { label: 'District Reports', url: 'index.html#reports-district' },
      { label: 'Facility Reports', url: 'index.html#reports-facility' },
      { label: 'Data Exports', url: 'index.html#reports-export' }
    ]},
    { label: 'Administration', icon: 'settings', subnav: [
      { label: 'Users & Roles', url: 'index.html#admin-users' },
      { label: 'Integrations', url: 'index.html#admin-integrations' },
      { label: 'Master Facility List', url: 'index.html#admin-mfl' },
      { label: 'DHIS2', url: 'index.html#admin-dhis2' },
      { label: 'Weather APIs', url: 'index.html#admin-weather' },
      { label: 'Sensors', url: 'index.html#admin-sensors' },
      { label: 'Audit Logs', url: 'index.html#admin-audit' }
    ]}
  ],
  district: [
    { label: 'District Dashboard', icon: 'crosshair', url: 'district.html' },
    { label: 'Early Warning', icon: 'zap', subnav: [
      { label: 'District Alerts', url: 'early-warning.html' },
      { label: 'Forecast', url: 'early-warning.html#forecast' },
      { label: 'Sensor Status', url: 'early-warning.html#sensors' }
    ]},
    { label: 'Healthcare Readiness', icon: 'hospital', subnav: [
      { label: 'Facility Readiness', url: 'healthcare.html#readiness' },
      { label: 'Disease Forecast', url: 'healthcare.html#forecast' },
      { label: 'Surge Planning', url: 'healthcare.html#surge' }
    ]},
    { label: 'Community Intelligence', icon: 'users', subnav: [
      { label: 'CHW Reports', url: 'district.html#chw' },
      { label: 'Verification', url: 'district.html#verify' }
    ]},
    { label: 'Facilities', icon: 'home', subnav: [
      { label: 'Health Facilities', url: 'district.html#facilities' },
      { label: 'Facility Performance', url: 'district.html#performance' }
    ]},
    { label: 'Reports', icon: 'file-text', url: 'district.html#reports' }
  ],
  worker: [
    { label: 'Home', icon: 'home', url: 'chw.html' },
    { label: 'Receive Alerts', icon: 'bell', url: 'chw.html#alerts' },
    { label: 'Patient Triage', icon: 'user-check', url: 'point-of-care.html' },
    { label: 'Community Reports', icon: 'message-square', url: 'chw.html#reports' },
    { label: 'Facility Status', icon: 'activity', url: 'chw.html#status' },
    { label: 'Health Assistant', icon: 'cpu', url: 'point-of-care.html#assistant' },
    { label: 'Profile', icon: 'user', url: 'chw.html#profile' }
  ],
  partner: [
    { label: 'National Dashboard', icon: 'crosshair', url: 'partner.html', view: 'impact' },
    { label: 'Maps', icon: 'map', url: 'partner.html', view: 'map' },
    { label: 'Forecasts', icon: 'trending-up', url: 'partner.html', view: 'forecasts' },
    { label: 'Impact Metrics', icon: 'pie-chart', url: 'partner.html', view: 'mne' },
    { label: 'Reports', icon: 'file-text', url: 'partner.html', view: 'reports' },
    { label: 'Downloads', icon: 'download', url: 'partner.html', view: 'downloads' }
  ]
};

function setRole(roleId, district = null) {
  if (ROLE_PERMISSIONS[roleId]) {
    localStorage.setItem(ROLE_KEY, roleId);
    if (district) localStorage.setItem(DISTRICT_KEY, district);
    else localStorage.removeItem(DISTRICT_KEY);
    window.location.href = ROLE_PERMISSIONS[roleId].page;
  }
}

function getRole() {
  return localStorage.getItem(ROLE_KEY) || 'admin'; // Default to admin
}

function getDistrict() {
  return localStorage.getItem(DISTRICT_KEY);
}

function requireRole() {
  const role = getRole();
  if (!role) {
    window.location.href = 'login.html';
    return null;
  }
  return role;
}

function logout() {
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(DISTRICT_KEY);
  window.location.href = 'login.html';
}

function renderSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;

  const role = getRole();
  const perms = ROLE_PERMISSIONS[role];
  const config = SIDEBAR_CONFIG[role];
  if (!perms || !config) return;

  const currentPath = window.location.pathname.split('/').pop() || 'index.html';
  
  const district = getDistrict();
  let subtitle = perms.name;
  if (district) subtitle += ` · ${district}`;

  let navHtml = '';
  
  config.forEach(item => {
    if (item.subnav) {
      // Group with sub-links
      const isExpanded = item.subnav.some(sub => currentPath.includes(sub.url.split('#')[0]));
      navHtml += `
        <div class="nav-section">
          <div class="nav-group ${isExpanded ? 'is-expanded' : ''}">
            <button class="nav-link nav-group__toggle" onclick="this.parentElement.classList.toggle('is-expanded')">
              <span class="nav-link__icon"><i data-lucide="${item.icon}"></i></span>
              <span class="nav-link__text">${item.label}</span>
              <i data-lucide="chevron-down" class="nav-group__chevron"></i>
            </button>
            <div class="nav-group__content">
              ${item.subnav.map(sub => {
                const isActive = currentPath.includes(sub.url.split('#')[0]);
                return `<a href="${sub.url}" class="nav-sublink ${isActive ? 'is-active' : ''}">${sub.label}</a>`;
              }).join('')}
            </div>
          </div>
        </div>
      `;
    } else {
      // Standalone link
      const isActive = currentPath.includes(item.url.split('#')[0]);
      const viewAttr = item.view ? ` data-view="${item.view}"` : '';
      navHtml += `
        <div class="nav-section">
          <a href="${item.url}"${viewAttr} class="nav-link ${isActive ? 'is-active' : ''}">
            <span class="nav-link__icon"><i data-lucide="${item.icon}"></i></span> ${item.label}
          </a>
        </div>
      `;
    }
  });

  sidebar.innerHTML = `
    <div class="sidebar__header">
      <a href="${perms.page}" class="sidebar__brand">
        <div class="sidebar__icon"><i data-lucide="globe"></i></div>
        <div>
          <div class="sidebar__title">CHEWS</div>
          <div class="sidebar__version" style="font-size:0.7rem;">${subtitle}</div>
        </div>
      </a>
    </div>
    <nav class="sidebar__nav">
      ${navHtml}
    </nav>
    <div class="sidebar__footer">
      <div class="sidebar__status"><span class="pulse-dot"></span><span>System Online · Sierra Leone</span></div>
      <button id="logout-btn" class="btn btn--ghost btn--sm" style="width: 100%; margin-top: 0.5rem;" onclick="logout()">Logout</button>
    </div>
  `;

  if (window.lucide) {
    lucide.createIcons();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  renderSidebar();
});
