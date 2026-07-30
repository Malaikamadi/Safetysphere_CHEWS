/**
 * CHEWS 4.0 — Role Management
 * Handles role-based access control, login, and sidebar filtering.
 */

const ROLE_KEY = 'chews-role';
const DISTRICT_KEY = 'chews-district';
const USER_KEY = 'chews-user';

const ROLE_PERMISSIONS = {
  'admin': {
    name: 'National Administrator',
    features: ['all'],
    nav: ['strategic-planning', 'early-warning', 'healthcare-readiness', 'point-of-care', 'ai-models'],
    page: 'index.html',
    initials: 'MO',
    fullName: 'Ministry of Health',
    subtitle: 'National Administrator'
  },
  'district': {
    name: 'District Health Officer',
    features: ['district-only'],
    nav: ['healthcare-readiness', 'early-warning', 'community-reports'],
    page: 'district.html',
    initials: 'DK',
    fullName: 'Dr. Kamara',
    subtitle: 'District Health Officer'
  },
  'worker': {
    name: 'Health Worker',
    features: ['facility-only'],
    nav: ['point-of-care', 'early-warning'],
    page: 'chw.html',
    initials: 'MM',
    fullName: 'Mariama',
    subtitle: 'Community Health Worker'
  },
  'partner': {
    name: 'Partner',
    features: ['analytics'],
    nav: ['ai-models', 'strategic-planning'],
    page: 'partner.html',
    initials: 'AS',
    fullName: 'Anna Smith',
    subtitle: 'Research Analyst'
  }
};

function setRole(roleId, district = null) {
  if (ROLE_PERMISSIONS[roleId]) {
    localStorage.setItem(ROLE_KEY, roleId);
    if (district) {
      localStorage.setItem(DISTRICT_KEY, district);
    } else {
      localStorage.removeItem(DISTRICT_KEY);
    }
    window.location.href = ROLE_PERMISSIONS[roleId].page;
  }
}

function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

function getDistrict() {
  return localStorage.getItem(DISTRICT_KEY);
}

function getRoleDetails() {
  const role = getRole();
  return role ? ROLE_PERMISSIONS[role] : null;
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

function updateSidebarForRole() {
  const role = getRole();
  if (!role) return;

  const perms = ROLE_PERMISSIONS[role];
  if (!perms) return;

  // Filter sidebar navigation
  const navGroups = document.querySelectorAll('.sidebar__nav .nav-group');
  navGroups.forEach(group => {
    const textEl = group.querySelector('.nav-link__text');
    if (!textEl) return;
    const text = textEl.textContent.trim().toLowerCase().replace(/\s+/g, '-');
    if (perms.features.includes('all') || perms.nav.includes(text)) {
        group.style.display = 'block';
    } else {
        group.style.display = 'none';
    }
  });

  // Update brand/version to show role
  const versionEl = document.querySelector('.sidebar__version');
  if (versionEl) {
    const district = getDistrict();
    let text = perms.name;
    if (district) text += ` · ${district}`;
    versionEl.textContent = text;
  }
  
  // Add logout button if not exists
  const footerEl = document.querySelector('.sidebar__footer');
  if (footerEl && !document.getElementById('logout-btn')) {
      const logoutBtn = document.createElement('button');
      logoutBtn.id = 'logout-btn';
      logoutBtn.className = 'btn btn--ghost btn--sm';
      logoutBtn.style.width = '100%';
      logoutBtn.style.marginTop = '0.5rem';
      logoutBtn.innerHTML = 'Logout';
      logoutBtn.onclick = logout;
      footerEl.appendChild(logoutBtn);
  }
}

// Call on load if we have a sidebar
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.sidebar__nav')) {
        updateSidebarForRole();
    }
});
