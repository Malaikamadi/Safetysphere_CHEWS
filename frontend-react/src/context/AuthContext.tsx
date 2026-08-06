import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'

// ── Types ──────────────────────────────────────────────────────────────────
export type Role = 'admin' | 'district' | 'worker' | 'partner'

export interface RoleConfig {
  name: string
  fullName: string
  initials: string
  subtitle: string
  homePath: string
}

export interface NavSubItem {
  label: string
  url: string
}

export interface NavItem {
  label: string
  icon: string
  url?: string
  view?: string
  subnav?: NavSubItem[]
}

// ── Role metadata ──────────────────────────────────────────────────────────
export const ROLE_CONFIG: Record<Role, RoleConfig> = {
  admin: {
    name: 'admin',
    fullName: 'National Administrator',
    initials: 'NA',
    subtitle: 'National Level · Sierra Leone',
    homePath: '/situation-room',
  },
  district: {
    name: 'district',
    fullName: 'District Health Officer',
    initials: 'DO',
    subtitle: 'District Level',
    homePath: '/district',
  },
  worker: {
    name: 'worker',
    fullName: 'Community Health Worker',
    initials: 'CW',
    subtitle: 'Community Level',
    homePath: '/chw',
  },
  partner: {
    name: 'partner',
    fullName: 'Development Partner',
    initials: 'DP',
    subtitle: 'Partner Access',
    homePath: '/partner',
  },
}

// ── Sidebar navigation config ──────────────────────────────────────────────
export const SIDEBAR_CONFIG: Record<Role, NavItem[]> = {
  admin: [
    { label: 'Command Center', icon: 'crosshair', url: '/situation-room' },
    {
      label: 'Strategic Planning', icon: 'map', subnav: [
        { label: 'National Risk Atlas', url: '/strategic#atlas' },
        { label: 'Facility Vulnerability', url: '/strategic#vulnerability' },
        { label: 'Pollution Monitoring', url: '/strategic#pollution' },
        { label: 'Carbon Dashboard', url: '/strategic#carbon' },
      ],
    },
    {
      label: 'Early Warning', icon: 'zap', subnav: [
        { label: 'Live Operations', url: '/early-warning' },
        { label: 'Alert Management', url: '/early-warning#alerts' },
        { label: 'Forecast Timeline', url: '/early-warning#forecast' },
        { label: 'Sensor Network', url: '/early-warning#sensors' },
      ],
    },
    {
      label: 'Healthcare Readiness', icon: 'hospital', subnav: [
        { label: 'Disease Forecast', url: '/healthcare#forecast' },
        { label: 'Facility Readiness', url: '/healthcare#readiness' },
        { label: 'Surge Planning', url: '/healthcare#surge' },
      ],
    },
    {
      label: 'Community Intelligence', icon: 'users', subnav: [
        { label: 'CHW Reports', url: '/#chw' },
        { label: 'Verification Queue', url: '/#queue' },
        { label: 'Community Alerts', url: '/#community-alerts' },
      ],
    },
    {
      label: 'Reports & Analytics', icon: 'bar-chart-2', subnav: [
        { label: 'Weekly Bulletin', url: '/report.html' },
        { label: 'Situation Reports', url: '/#reports-sitrep' },
        { label: 'Data Exports', url: '/#reports-export' },
      ],
    },
    {
      label: 'AI Models', icon: 'cpu', url: '/ai-models',
    },
    {
      label: 'Administration', icon: 'settings', subnav: [
        { label: 'Users & Roles', url: '/#admin-users' },
        { label: 'Integrations', url: '/#admin-integrations' },
        { label: 'DHIS2', url: '/#admin-dhis2' },
        { label: 'Sensors', url: '/#admin-sensors' },
        { label: 'Audit Logs', url: '/#admin-audit' },
      ],
    },
  ],
  district: [
    { label: 'District Dashboard', icon: 'crosshair', url: '/district' },
    {
      label: 'Early Warning', icon: 'zap', subnav: [
        { label: 'District Alerts', url: '/early-warning' },
        { label: 'Forecast', url: '/early-warning#forecast' },
        { label: 'Sensor Status', url: '/early-warning#sensors' },
      ],
    },
    {
      label: 'Healthcare Readiness', icon: 'hospital', subnav: [
        { label: 'Facility Readiness', url: '/healthcare#readiness' },
        { label: 'Disease Forecast', url: '/healthcare#forecast' },
        { label: 'Surge Planning', url: '/healthcare#surge' },
      ],
    },
    {
      label: 'Community Intelligence', icon: 'users', subnav: [
        { label: 'CHW Reports', url: '/district#chw' },
        { label: 'Verification', url: '/district#verify' },
      ],
    },
    {
      label: 'Facilities', icon: 'home', subnav: [
        { label: 'Health Facilities', url: '/district#facilities' },
        { label: 'Facility Performance', url: '/district#performance' },
      ],
    },
    { label: 'Reports', icon: 'file-text', url: '/district#reports' },
  ],
  worker: [
    { label: 'Home', icon: 'home', url: '/chw' },
    { label: 'Receive Alerts', icon: 'bell', url: '/chw#alerts' },
    { label: 'Patient Triage', icon: 'user-check', url: '/poc' },
    { label: 'Community Reports', icon: 'message-square', url: '/chw#reports' },
    { label: 'Facility Status', icon: 'activity', url: '/chw#status' },
    { label: 'Health Assistant', icon: 'cpu', url: '/poc#assistant' },
    { label: 'Profile', icon: 'user', url: '/chw#profile' },
  ],
  partner: [
    { label: 'National Dashboard', icon: 'crosshair', url: '/partner' },
    { label: 'Maps', icon: 'map', url: '/partner#map' },
    { label: 'Forecasts', icon: 'trending-up', url: '/partner#forecasts' },
    { label: 'Impact Metrics', icon: 'pie-chart', url: '/partner#mne' },
    { label: 'Reports', icon: 'file-text', url: '/partner#reports' },
    { label: 'Downloads', icon: 'download', url: '/partner#downloads' },
  ],
}

// ── Context ────────────────────────────────────────────────────────────────
interface AuthContextValue {
  role: Role | null
  district: string | null
  roleConfig: RoleConfig | null
  login: (role: Role, district?: string) => void
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

const ROLE_KEY = 'chews-role'
const DISTRICT_KEY = 'chews-district'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<Role | null>(() => {
    const stored = localStorage.getItem(ROLE_KEY)
    return (stored as Role) || null
  })
  const [district, setDistrict] = useState<string | null>(() =>
    localStorage.getItem(DISTRICT_KEY)
  )

  const login = useCallback((newRole: Role, newDistrict?: string) => {
    localStorage.setItem(ROLE_KEY, newRole)
    if (newDistrict) {
      localStorage.setItem(DISTRICT_KEY, newDistrict)
      setDistrict(newDistrict)
    } else {
      localStorage.removeItem(DISTRICT_KEY)
      setDistrict(null)
    }
    setRole(newRole)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(ROLE_KEY)
    localStorage.removeItem(DISTRICT_KEY)
    setRole(null)
    setDistrict(null)
  }, [])

  const roleConfig = role ? ROLE_CONFIG[role] : null

  return (
    <AuthContext.Provider value={{ role, district, roleConfig, login, logout, isAuthenticated: !!role }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
