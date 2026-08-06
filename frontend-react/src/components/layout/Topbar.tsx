import { Sun, Moon, Bell } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../hooks/useTheme'
import styles from './Topbar.module.css'

interface Props {
  title?: string
  subtitle?: string
}

export default function Topbar({ title, subtitle }: Props) {
  const { roleConfig } = useAuth()
  const { theme, toggle } = useTheme()

  const now = new Date()
  const dateStr = now.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  const timeStr = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        {title && <h1 className={styles.title}>{title}</h1>}
        {subtitle && <span className={styles.subtitle}>{subtitle}</span>}
      </div>

      <div className={styles.right}>
        <span className={styles.timestamp}>Last updated: {dateStr}, {timeStr}</span>

        <button className={styles.iconBtn} onClick={toggle} aria-label="Toggle theme">
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        <button className={styles.iconBtn} aria-label="Notifications">
          <Bell size={16} />
        </button>

        <div className={styles.avatar}>
          <span className={styles.avatarInitials}>{roleConfig?.initials ?? 'U'}</span>
          <div className={styles.avatarInfo}>
            <span className={styles.avatarName}>{roleConfig?.fullName ?? 'User'}</span>
            <span className={styles.avatarRole}>{roleConfig?.subtitle ?? ''}</span>
          </div>
        </div>
      </div>
    </header>
  )
}
