import { useState, useCallback } from 'react'
import L from 'leaflet'
import { api } from '../api/client'
import LeafletMap from '../components/map/LeafletMap'
import RiskBadge from '../components/ui/RiskBadge'
import StatCard from '../components/ui/StatCard'
import styles from './Strategic.module.css'

export default function Strategic() {
  const [form, setForm] = useState({ rainfall: 120, temperature: 28, humidity: 82, elevation: 50, drainage_quality: 2, soil_saturation: 75 })
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  async function runPredict() {
    setLoading(true)
    try {
      const res = await api.strategicPredict(form as any)
      setResult(res)
    } catch { setResult({ error: 'Backend offline' }) }
    setLoading(false)
  }

  const handleMapReady = useCallback((map: L.Map) => {
    api.floodDashboard().then((d: any) => {
      d?.flood_zones?.slice(0, 20).forEach((z: any) => {
        L.circleMarker([z.lat, z.lng], {
          radius: 12, fillColor: '#6f8faa', color: '#4a7a9b', fillOpacity: 0.6, weight: 1,
        }).bindTooltip(`<strong>${z.name}</strong><br/>Flood Risk: ${(z.flood_risk * 100).toFixed(0)}%`).addTo(map)
      })
    }).catch(() => {})
  }, [])

  const POLLUTION_DATA = [
    { name: 'Freetown West',  aqi: 42, pm25: 12, pm10: 24, status: 'Good' },
    { name: 'Freetown East',  aqi: 71, pm25: 24, pm10: 48, status: 'Moderate' },
    { name: 'Bo City',        aqi: 55, pm25: 18, pm10: 36, status: 'Moderate' },
    { name: 'Kenema Town',    aqi: 38, pm25: 10, pm10: 20, status: 'Good' },
  ]

  return (
    <div className={styles.page}>
      <div>
        <h2>Strategic Planning</h2>
        <p className={styles.desc}>National risk atlas, flood modelling, pollution monitoring, and carbon accounting</p>
      </div>

      <div className={styles.kpiGrid}>
        <StatCard value="16" label="Districts Monitored" colour="blue" />
        <StatCard value="23" label="Flood-Prone Zones"  colour="orange" />
        <StatCard value="4"  label="AQI Stations"       colour="green" />
        <StatCard value="0.74" label="National Risk Index" colour="red" />
      </div>

      <div className={styles.twoCol}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Flood Risk Atlas</h3>
          <LeafletMap onMapReady={handleMapReady} style={{ height: 380 }} />
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Risk Prediction Tool</h3>
          <div className={styles.formGrid}>
            {[
              { label: 'Rainfall 24h (mm)', key: 'rainfall' },
              { label: 'Temperature (°C)',  key: 'temperature' },
              { label: 'Humidity (%)',       key: 'humidity' },
              { label: 'Elevation (m)',      key: 'elevation' },
              { label: 'Soil Saturation %', key: 'soil_saturation' },
            ].map(f => (
              <label key={f.key} className={styles.formField}>
                <span>{f.label}</span>
                <input type="number" value={(form as any)[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: +e.target.value }))} className={styles.input} />
              </label>
            ))}
          </div>
          <button className={styles.runBtn} onClick={runPredict} disabled={loading}>
            {loading ? 'Computing…' : 'Run Assessment'}
          </button>
          {result && !result.error && (
            <div className={styles.resultBox}>
              <RiskBadge level={result.risk_level ?? 'Unknown'} />
              <div className={styles.resultScore}>Score: <strong>{(result.final_risk ?? result.risk_score ?? 0).toFixed(3)}</strong></div>
              {result.explanation && <p className={styles.resultExplain}>{result.explanation}</p>}
            </div>
          )}
          {result?.error && <p className={styles.errorMsg}>{result.error}</p>}
        </div>
      </div>

      {/* Pollution */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Air Quality Monitoring</h3>
        <table className={styles.table}>
          <thead><tr><th>Station</th><th>AQI</th><th>PM2.5</th><th>PM10</th><th>Status</th></tr></thead>
          <tbody>
            {POLLUTION_DATA.map(p => (
              <tr key={p.name}>
                <td><strong>{p.name}</strong></td>
                <td className={styles.metric}>{p.aqi}</td>
                <td className={styles.metric}>{p.pm25} μg/m³</td>
                <td className={styles.metric}>{p.pm10} μg/m³</td>
                <td><RiskBadge level={p.aqi > 100 ? 'high' : p.aqi > 50 ? 'moderate' : 'low'} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
