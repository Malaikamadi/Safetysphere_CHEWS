import styles from './RiskBadge.module.css'

type RiskLevel = 'low' | 'moderate' | 'medium' | 'high' | 'critical' | 'extreme'

interface Props {
  level: RiskLevel | string
  score?: number
}

function normalise(level: string): RiskLevel {
  const l = level.toLowerCase()
  if (l === 'medium') return 'moderate'
  if (['low','moderate','high','critical','extreme'].includes(l)) return l as RiskLevel
  return 'low'
}

export default function RiskBadge({ level }: Props) {
  const norm = normalise(level)
  return <span className={`${styles.badge} ${styles[norm]}`}>{level}</span>
}
