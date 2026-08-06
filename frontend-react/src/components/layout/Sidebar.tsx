import { NavLink, useLocation } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { useAuth, SIDEBAR_CONFIG, type NavItem } from '../../context/AuthContext'
import styles from './Sidebar.module.css'

// Simple text-icon mapping using emoji/unicode for nav items
const NAV_ICONS: Record<string, string> = {
  crosshair: '⊕', map: '🗺', zap: '⚡', hospital: '🏥', users: '👥',
  'bar-chart-2': '📊', cpu: '🤖', settings: '⚙', home: '🏠', bell: '🔔',
  'user-check': '✅', 'message-square': '💬', activity: '📈', user: '👤',
  'trending-up': '📉', 'pie-chart': '🥧', 'file-text': '📄', download: '⬇',
}

function NavIcon({ name }: { name: string }) {
  return <span style={{ fontSize: '0.9rem' }}>{NAV_ICONS[name] ?? '•'}</span>
}

function NavGroup({ item }: { item: NavItem }) {
  const location = useLocation()
  const isExpanded = item.subnav?.some(s => location.pathname.startsWith(s.url.split('#')[0])) ?? false
  const [open, setOpen] = useState(isExpanded)

  return (
    <div className={styles.navSection}>
      <button className={styles.groupToggle} onClick={() => setOpen(o => !o)}>
        <span className={styles.navIcon}><NavIcon name={item.icon} /></span>
        <span className={styles.navLabel}>{item.label}</span>
        <ChevronDown
          size={14}
          className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}
        />
      </button>
      {open && (
        <div className={styles.subnav}>
          {item.subnav?.map(sub => (
            <NavLink
              key={sub.url}
              to={sub.url}
              className={({ isActive }) =>
                `${styles.sublink} ${isActive ? styles.sublinkActive : ''}`
              }
            >
              {sub.label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Sidebar() {
  const { role, roleConfig, district, logout } = useAuth()

  if (!role || !roleConfig) return null

  const navItems = SIDEBAR_CONFIG[role]
  const subtitle = district ? `${roleConfig.subtitle} · ${district}` : roleConfig.subtitle

  return (
    <aside className={styles.sidebar} id="sidebar">
      <div className={styles.header}>
        <NavLink to={roleConfig.homePath} className={styles.brand}>
          <div className={styles.logoBox}>
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
          </div>
          <div>
            <div className={styles.brandName}>CHEWS</div>
            <div className={styles.brandSub}>{subtitle}</div>
          </div>
        </NavLink>
      </div>

      <nav className={styles.nav}>
        {navItems.map((item) =>
          item.subnav ? (
            <NavGroup key={item.label} item={item} />
          ) : (
            <div key={item.label} className={styles.navSection}>
              <NavLink
                to={item.url ?? '/'}
                className={({ isActive }) =>
                  `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`
                }
              >
                <span className={styles.navIcon}><NavIcon name={item.icon} /></span>
                <span className={styles.navLabel}>{item.label}</span>
              </NavLink>
            </div>
          )
        )}
      </nav>

      <div className={styles.footer}>
        <div className={styles.status}>
          <span className="pulse-dot" />
          <span>System Online · Sierra Leone</span>
        </div>
        <button className={styles.logoutBtn} onClick={logout}>Logout</button>
      </div>
    </aside>
  )
}
