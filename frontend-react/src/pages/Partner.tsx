import { useCallback } from 'react'
import L from 'leaflet'
import LeafletMap from '../components/map/LeafletMap'
import StatCard from '../components/ui/StatCard'
import RiskBadge from '../components/ui/RiskBadge'
import styles from './Partner.module.css'

export default function Partner() {
  const handleMapReady = useCallback((map: L.Map) => {
    map.setView([8.46, -11.78], 7)
  }, [])

  const METRICS = [
    { label: 'People Reached (LLINs)', value: '1.2M', trend: '+8% vs last Q' },
    { label: 'Facilities Supported',   value: '142',  trend: 'Active' },
    { label: 'CHWs Trained',           value: '2,840', trend: 'This year' },
    { label: 'Districts Covered',      value: '12',    trend: 'of 16' },
  ]

  const FORECASTS = [
    { disease: 'Malaria',   current: 'High',     next14d: 'Critical', pop: '1.2M' },
    { disease: 'Cholera',   current: 'Moderate', next14d: 'High',     pop: '450K' },
    { disease: 'Dengue',    current: 'Low',      next14d: 'Moderate', pop: '180K' },
  ]

  return (
    <div className={styles.page}>
      <div>
        <h2>Partner Intelligence Dashboard</h2>
        <p className={styles.desc}>National health intelligence and impact metrics for development partners</p>
      </div>

      <div className={styles.kpiGrid}>
        {METRICS.map(m => (
          <div key={m.label} className={styles.metricCard}>
            <div className={styles.metricValue}>{m.value}</div>
            <div className={styles.metricLabel}>{m.label}</div>
            <div className={styles.metricTrend}>{m.trend}</div>
          </div>
        ))}
      </div>

      <div className={styles.twoCol}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>National Risk Map</h3>
          <LeafletMap onMapReady={handleMapReady} style={{ height: 380 }} />
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Disease Outlook (14 Days)</h3>
          <table className={styles.table}>
            <thead>
              <tr><th>Disease</th><th>Current</th><th>14-Day</th><th>Pop. at Risk</th></tr>
            </thead>
            <tbody>
              {FORECASTS.map(f => (
                <tr key={f.disease}>
                  <td><strong>{f.disease}</strong></td>
                  <td><RiskBadge level={f.current} /></td>
                  <td><RiskBadge level={f.next14d} /></td>
                  <td className={styles.popCell}>{f.pop}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className={styles.downloadSection}>
            <h4 className={styles.downloadTitle}>Export & Reports</h4>
            <div className={styles.downloadBtns}>
              <a href="/report.html" target="_blank" className={styles.downloadBtn}>
                📄 Weekly Bulletin (PDF)
              </a>
              <button className={styles.downloadBtn}>📊 Data Export (CSV)</button>
              <button className={styles.downloadBtn}>🗺 Shapefiles (GIS)</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
