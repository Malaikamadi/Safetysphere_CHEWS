import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth, type Role, ROLE_CONFIG } from '../context/AuthContext'
import styles from './Login.module.css'

const ROLES: { id: Role; label: string; description: string; icon: string }[] = [
  { id: 'admin',    label: 'National Administrator', description: 'Full system access · Command Centre', icon: '🛡️' },
  { id: 'district', label: 'District Health Officer', description: 'District-level analytics & alerts',  icon: '🏥' },
  { id: 'worker',   label: 'Community Health Worker',description: 'Field reporting & patient triage',   icon: '👩‍⚕️' },
  { id: 'partner',  label: 'Development Partner',    description: 'Impact metrics & data exports',       icon: '🤝' },
]

const DISTRICTS = [
  'Bo','Bombali','Bonthe','Falaba','Kailahun','Kambia','Karene',
  'Kenema','Koinadugu','Kono','Moyamba','Port Loko','Pujehun',
  'Tonkolili','Western Area Rural','Western Area Urban',
]

export default function Login() {
  const { login, isAuthenticated, roleConfig } = useAuth()
  const [selected, setSelected] = useState<Role | null>(null)
  const [district, setDistrict] = useState('')

  if (isAuthenticated && roleConfig) {
    return <Navigate to={roleConfig.homePath} replace />
  }

  function handleLogin() {
    if (!selected) return
    login(selected, selected === 'district' ? district || undefined : undefined)
  }

  return (
    <div className={styles.page}>
      <div className="bg-animation" aria-hidden="true">
        <div className="bg-orb bg-orb--1" /><div className="bg-orb bg-orb--2" />
        <div className="bg-orb bg-orb--3" /><div className="bg-orb bg-orb--4" />
      </div>

      <div className={styles.card}>
        <div className={styles.brand}>
          <div className={styles.logoBox}>
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="24" height="24">
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
          </div>
          <div>
            <div className={styles.brandName}>CHEWS</div>
            <div className={styles.brandSub}>Climate & Health Early Warning System</div>
          </div>
        </div>

        <h1 className={styles.title}>Select Your Role</h1>
        <p className={styles.subtitle}>Choose your access level to continue</p>

        <div className={styles.roleGrid}>
          {ROLES.map(r => (
            <button
              key={r.id}
              className={`${styles.roleCard} ${selected === r.id ? styles.roleCardSelected : ''}`}
              onClick={() => setSelected(r.id)}
            >
              <span className={styles.roleIcon}>{r.icon}</span>
              <div>
                <div className={styles.roleLabel}>{r.label}</div>
                <div className={styles.roleDesc}>{r.description}</div>
              </div>
            </button>
          ))}
        </div>

        {selected === 'district' && (
          <div className={styles.districtSelect}>
            <label className={styles.selectLabel}>Select District</label>
            <select
              className={styles.select}
              value={district}
              onChange={e => setDistrict(e.target.value)}
            >
              <option value="">— Choose district —</option>
              {DISTRICTS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        )}

        <button
          className={styles.loginBtn}
          disabled={!selected}
          onClick={handleLogin}
        >
          Continue as {selected ? ROLE_CONFIG[selected].fullName : '…'}
        </button>

        <p className={styles.footer}>Sierra Leone · CHEWS v4.0 · SafetySphere</p>
      </div>
    </div>
  )
}
