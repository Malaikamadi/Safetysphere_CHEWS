import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import RiskBadge from '../components/ui/RiskBadge'
import StatCard from '../components/ui/StatCard'
import styles from './Healthcare.module.css'

export default function Healthcare() {
  const [forecastForm, setForecastForm] = useState({ reported_cases: 120, rainfall: 85, temperature: 28, humidity: 80, trend: 'increasing' })
  const [forecastResult, setForecastResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  async function runForecast() {
    setLoading(true)
    try {
      const res = await api.healthcareForecast(forecastForm as any)
      setForecastResult(res)
    } catch { setForecastResult({ error: 'Backend offline' }) }
    setLoading(false)
  }

  const READINESS_CATEGORIES = [
    { name: 'Medicines & RDTs',  score: 58, color: 'var(--orange)' },
    { name: 'Health Workforce',  score: 72, color: 'var(--green)'  },
    { name: 'Medical Equipment', score: 65, color: 'var(--orange)' },
    { name: 'Electricity',       score: 45, color: 'var(--red)'    },
    { name: 'WASH / Water',      score: 52, color: 'var(--orange)' },
    { name: 'Referral Network',  score: 80, color: 'var(--green)'  },
    { name: 'Cold Chain',        score: 61, color: 'var(--orange)' },
  ]

  const FACILITY_TABLE = [
    { name: 'Koinadugu District Hospital', type: 'District Hospital', readiness: 38, malaria: 'High', flood: 'Critical' },
    { name: 'Bombali MCHC',                type: 'MCHC',             readiness: 46, malaria: 'High', flood: 'High'     },
    { name: 'Port Loko GH',                type: 'Government Hospital', readiness: 55, malaria: 'High', flood: 'Moderate' },
    { name: 'Kambia District Hospital',    type: 'District Hospital', readiness: 63, malaria: 'Moderate', flood: 'Low' },
    { name: 'Kenema GH',                   type: 'Government Hospital', readiness: 71, malaria: 'Moderate', flood: 'Low' },
  ]

  return (
    <div className={styles.page}>
      <div>
        <h2>Healthcare Readiness</h2>
        <p className={styles.desc}>Disease forecasting, facility readiness monitoring, and surge planning</p>
      </div>

      <div className={styles.kpiGrid}>
        <StatCard value="62%" label="National Readiness Index" colour="orange" />
        <StatCard value="34%" label="Facilities Under Strain" colour="red" />
        <StatCard value="16"  label="Districts Monitored" colour="blue" />
        <StatCard value="3"   label="Critical Facilities" colour="red" />
      </div>

      <div className={styles.twoCol}>
        {/* Readiness Breakdown */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>National Readiness Breakdown</h3>
          <div className={styles.readinessBars}>
            {READINESS_CATEGORIES.map(c => (
              <div key={c.name} className={styles.readinessRow}>
                <span className={styles.readinessLabel}>{c.name}</span>
                <div className={styles.readinessTrack}>
                  <div className={styles.readinessFill} style={{ width: `${c.score}%`, background: c.color }} />
                </div>
                <span className={styles.readinessVal}>{c.score}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Disease Forecast Tool */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Disease Forecast Tool</h3>
          <div className={styles.formGrid}>
            {[
              { label: 'Reported Cases', key: 'reported_cases', type: 'number' },
              { label: 'Rainfall (mm)', key: 'rainfall', type: 'number' },
              { label: 'Temperature (°C)', key: 'temperature', type: 'number' },
              { label: 'Humidity (%)', key: 'humidity', type: 'number' },
            ].map(f => (
              <label key={f.key} className={styles.formField}>
                <span>{f.label}</span>
                <input
                  type={f.type}
                  value={(forecastForm as any)[f.key]}
                  onChange={e => setForecastForm(prev => ({ ...prev, [f.key]: +e.target.value }))}
                  className={styles.input}
                />
              </label>
            ))}
            <label className={styles.formField}>
              <span>Trend</span>
              <select className={styles.input} value={forecastForm.trend} onChange={e => setForecastForm(p => ({ ...p, trend: e.target.value }))}>
                <option value="increasing">Increasing</option>
                <option value="stable">Stable</option>
                <option value="decreasing">Decreasing</option>
              </select>
            </label>
          </div>
          <button className={styles.runBtn} onClick={runForecast} disabled={loading}>
            {loading ? 'Running…' : 'Run Forecast'}
          </button>
          {forecastResult && !forecastResult.error && (
            <div className={styles.forecastOutput}>
              <div className={styles.forecastScore}>
                Risk Score: <strong>{forecastResult.risk_score?.toFixed(2) ?? forecastResult.final_risk?.toFixed(2)}</strong>
              </div>
              <RiskBadge level={forecastResult.risk_level ?? 'Unknown'} />
              {forecastResult.explanation && <p className={styles.forecastExplain}>{forecastResult.explanation}</p>}
            </div>
          )}
          {forecastResult?.error && <p className={styles.errorMsg}>{forecastResult.error}</p>}
        </div>
      </div>

      {/* Facility Table */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Priority Facility Status</h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Facility</th><th>Type</th><th>Readiness</th>
              <th>Malaria Risk</th><th>Flood Exposure</th>
            </tr>
          </thead>
          <tbody>
            {FACILITY_TABLE.map(f => (
              <tr key={f.name}>
                <td><strong>{f.name}</strong></td>
                <td className={styles.typCell}>{f.type}</td>
                <td>
                  <div className={styles.miniBar}>
                    <div style={{ width: `${f.readiness}%`, background: f.readiness < 50 ? 'var(--red)' : f.readiness < 70 ? 'var(--orange)' : 'var(--green)' }} />
                  </div>
                  <span className={styles.miniBarVal}>{f.readiness}%</span>
                </td>
                <td><RiskBadge level={f.malaria} /></td>
                <td><RiskBadge level={f.flood} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
