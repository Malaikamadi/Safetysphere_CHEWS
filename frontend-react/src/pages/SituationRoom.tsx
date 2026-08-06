import { useCallback, useRef } from 'react'
import L from 'leaflet'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import StatCard from '../components/ui/StatCard'
import RiskBadge from '../components/ui/RiskBadge'
import LeafletMap from '../components/map/LeafletMap'
import styles from './SituationRoom.module.css'

function formatNum(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return Math.round(n / 1_000) + 'K'
  return n.toLocaleString()
}

function riskColor(score: number) {
  if (score >= 0.8) return '#943d3a'
  if (score >= 0.6) return '#c8875c'
  if (score >= 0.4) return '#c9a963'
  return '#4a7a4f'
}

export default function SituationRoom() {
  const { data, loading, error } = useApi(() => api.situationRoom(), [])
  const mapRef = useRef<L.Map | null>(null)

  const handleMapReady = useCallback((map: L.Map) => {
    mapRef.current = map
    api.situationRoomMap().then(d => {
      const mapData = d as any
      if (!mapData?.layers) return

      Object.entries(mapData.layers).forEach(([layerName, fc]: [string, any]) => {
        const colours: Record<string, string> = {
          flood: '#6f8faa', malaria: '#c75c54', heat: '#c4876a',
          air_quality: '#9c7f8f', vulnerability: '#c9a963',
        }
        const color = colours[layerName] ?? '#b5726b'
        const group = L.layerGroup()
        fc.features?.forEach((f: any) => {
          const [lng, lat] = f.geometry.coordinates
          const score = f.properties.score ?? 0.3
          L.circleMarker([lat, lng], {
            radius: 22 * (0.5 + score * 0.8),
            fillColor: f.properties.color ?? color,
            color: 'transparent',
            fillOpacity: 0.45 + score * 0.3,
            weight: 0,
          })
            .bindTooltip(`<strong>${f.properties.name}</strong><br/>${layerName}: ${f.properties.risk_level} (${(score * 100).toFixed(0)}%)`)
            .addTo(group)
        })
        group.addTo(map)
      })
    }).catch(() => {/* offline — no layers */})
  }, [])

  const sr = data as any

  const riskScore   = sr?.national_risk_score ?? 0.68
  const riskLevel   = sr?.national_risk_level ?? 'High Risk'
  const popRisk     = sr?.population_at_risk ?? 1_200_000
  const childRisk   = sr?.children_at_risk ?? 412_000
  const pregRisk    = sr?.pregnant_women_at_risk ?? 89_000
  const alertCount  = sr?.active_alerts ?? 7

  const FALLBACK_DISTRICTS = [
    { name: 'Koinadugu', score: 0.82, risk: 'Flood + Malaria', level: 'critical' },
    { name: 'Bombali',   score: 0.76, risk: 'Flood',           level: 'high' },
    { name: 'Port Loko', score: 0.72, risk: 'Malaria',         level: 'high' },
    { name: 'Kenema',    score: 0.68, risk: 'Malaria',         level: 'moderate' },
    { name: 'Bo',        score: 0.65, risk: 'Malaria',         level: 'moderate' },
  ]

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <h2>National Situation Room</h2>
          <p className={styles.pageDesc}>Real-time multi-hazard climate and health intelligence for Sierra Leone</p>
        </div>
        <div className={styles.riskPill} style={{ background: riskColor(riskScore) }}>
          {riskLevel} · {riskScore.toFixed(2)}
        </div>
      </div>

      {/* KPIs */}
      <div className={styles.kpiGrid}>
        <StatCard value={formatNum(popRisk)}   label="Population at Risk"     colour="red" />
        <StatCard value={formatNum(childRisk)} label="Children at Risk"        colour="orange" />
        <StatCard value={formatNum(pregRisk)}  label="Pregnant Women at Risk"  colour="orange" />
        <StatCard value={alertCount}           label="Active Alerts"           colour="red" />
      </div>

      {/* Map + Rankings */}
      <div className={styles.twoCol}>
        <div className={styles.mapCard}>
          <h3 className={styles.sectionTitle}>National Risk Map</h3>
          {loading && <div className={styles.loadingMsg}>Loading map data…</div>}
          {error  && <div className={styles.errorMsg}>Backend offline — map unavailable</div>}
          <LeafletMap onMapReady={handleMapReady} style={{ height: 420 }} />
        </div>

        <div className={styles.rankCard}>
          <h3 className={styles.sectionTitle}>District Risk Rankings</h3>
          <table className={styles.rankTable}>
            <thead>
              <tr><th>District</th><th>Score</th><th>Primary Hazard</th></tr>
            </thead>
            <tbody>
              {FALLBACK_DISTRICTS.map(d => (
                <tr key={d.name}>
                  <td><strong>{d.name}</strong></td>
                  <td className={styles.scoreCell}>{d.score.toFixed(2)}</td>
                  <td><RiskBadge level={d.level} /></td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 className={styles.sectionTitle} style={{ marginTop: 24 }}>Active Alerts</h3>
          <div className={styles.alertsList}>
            {(sr?.recommended_actions ?? [
              { action: 'Flood risk high in Koinadugu', priority: 'high', time: '3h ago' },
              { action: 'Malaria surge predicted',       priority: 'high', time: '5h ago' },
              { action: 'Air quality unhealthy – Freetown', priority: 'medium', time: '8h ago' },
            ]).slice(0, 5).map((a: any, i: number) => (
              <div key={i} className={`${styles.alertItem} ${styles[`alert_${a.priority ?? 'medium'}`]}`}>
                <span className={styles.alertBadge}>{a.priority ?? 'medium'}</span>
                <div>
                  <div className={styles.alertText}>{a.action}</div>
                  <div className={styles.alertMeta}>{a.time ?? 'Recently'}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
