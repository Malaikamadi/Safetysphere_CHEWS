import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import StatCard from '../components/ui/StatCard'
import styles from './AIModels.module.css'

const MODELS = [
  { name: 'Flood Risk Model', algorithm: 'GradientBoosting Classifier', metric: 'AUC', score: 0.991, status: 'Production', description: 'Predicts probability of severe flooding given climate and terrain inputs.' },
  { name: 'Malaria Predictor', algorithm: 'GradientBoosting Regressor', metric: 'R²', score: 0.618, status: 'Production', description: 'Forecasts malaria incidence rate from rainfall, temperature, and historical burden.' },
  { name: 'Healthcare Readiness', algorithm: 'RandomForest Regressor', metric: 'R²', score: 0.881, status: 'Production', description: 'Composite score of facility capacity across 7 readiness dimensions.' },
  { name: 'Community Triage', algorithm: 'RandomForest Classifier', metric: 'F1', score: null, status: 'Validation', description: 'AI-assisted patient prioritisation at point of care.' },
]

const FEATURE_IMPORTANCE = [
  { name: 'Cumulative Rainfall (14d)', importance: 0.42 },
  { name: 'River Discharge Index',     importance: 0.26 },
  { name: 'Historical Incidence',      importance: 0.18 },
  { name: 'Soil Moisture Index',       importance: 0.14 },
]

export default function AIModels() {
  const { data, loading } = useApi(() => api.health(), [])
  const health = data as any

  return (
    <div className={styles.page}>
      <div>
        <h2>AI Model Intelligence</h2>
        <p className={styles.desc}>Model performance, explainability, and health monitoring</p>
      </div>

      <div className={styles.kpiGrid}>
        <StatCard value="4"    label="Active Models"     colour="blue"   />
        <StatCard value="3"    label="In Production"     colour="green"  />
        <StatCard value="0.991" label="Best AUC"          colour="green"  />
        <StatCard value={loading ? '…' : health ? '✓ Online' : '✗ Offline'} label="Backend Status" colour={health ? 'green' : 'red'} />
      </div>

      <div className={styles.modelGrid}>
        {MODELS.map(m => (
          <div key={m.name} className={`${styles.modelCard} ${m.status === 'Validation' ? styles.modelValidation : ''}`}>
            <div className={styles.modelHeader}>
              <span className={styles.modelName}>{m.name}</span>
              <span className={`${styles.modelStatus} ${m.status === 'Production' ? styles.statusProd : styles.statusVal}`}>
                {m.status}
              </span>
            </div>
            <div className={styles.modelAlgo}>{m.algorithm}</div>
            <p className={styles.modelDesc}>{m.description}</p>
            <div className={styles.modelScore}>
              <span className={styles.metricLabel}>{m.metric}</span>
              <span className={styles.metricValue}>{m.score !== null ? m.score.toFixed(3) : '—'}</span>
              {m.score !== null && (
                <div className={styles.scoreBar}>
                  <div className={styles.scoreFill} style={{ width: `${m.score * 100}%`, background: m.score > 0.85 ? 'var(--green)' : m.score > 0.7 ? 'var(--orange)' : 'var(--red)' }} />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Feature Importance — Composite Risk Model</h3>
        <p className={styles.cardDesc}>SHAP-based contributions to the national risk index prediction.</p>
        <div className={styles.featureBars}>
          {FEATURE_IMPORTANCE.map(f => (
            <div key={f.name} className={styles.featureRow}>
              <span className={styles.featureName}>{f.name}</span>
              <div className={styles.featureTrack}>
                <div className={styles.featureFill} style={{ width: `${f.importance * 100}%` }} />
              </div>
              <span className={styles.featurePct}>{(f.importance * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.dataSourcesCard}>
        <h3 className={styles.cardTitle}>Training Data Sources</h3>
        <div className={styles.sourceGrid}>
          {[
            { name: 'DHIS2',        desc: 'Routine health surveillance',     records: '2.4M rows' },
            { name: 'CHIRPS',       desc: 'Satellite precipitation',          records: '1985–2025' },
            { name: 'ERA5',         desc: 'Climate reanalysis',               records: '40y data'  },
            { name: 'WorldPop',     desc: 'Population grids 100m',            records: '2025 Est.' },
            { name: 'Master Facility List', desc: 'Facility registry',         records: '1,200+ facilities' },
            { name: 'OpenStreetMap',  desc: 'Road & waterway networks',       records: 'Live sync' },
          ].map(s => (
            <div key={s.name} className={styles.sourceItem}>
              <div className={styles.sourceName}>{s.name}</div>
              <div className={styles.sourceDesc}>{s.desc}</div>
              <div className={styles.sourceRecords}>{s.records}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
