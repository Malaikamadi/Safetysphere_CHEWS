import styles from './StatCard.module.css'

interface Props {
  value: string | number
  label: string
  colour?: 'blue' | 'green' | 'orange' | 'red' | 'default'
  subtitle?: string
}

export default function StatCard({ value, label, colour = 'default', subtitle }: Props) {
  return (
    <div className={`${styles.card} ${styles[colour]}`}>
      <div className={styles.value}>{value}</div>
      <div className={styles.label}>{label}</div>
      {subtitle && <div className={styles.subtitle}>{subtitle}</div>}
    </div>
  )
}
