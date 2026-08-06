import { useState, useCallback, useRef } from 'react'
import L from 'leaflet'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import RiskBadge from '../components/ui/RiskBadge'
import StatCard from '../components/ui/StatCard'
import LeafletMap from '../components/map/LeafletMap'
import styles from './EarlyWarning.module.css'

const TABS = ['Alerts', 'Forecast', 'Sensors', 'EOC Map'] as const
type Tab = typeof TABS[number]

export default function EarlyWarning() {
  const [activeTab, setActiveTab] = useState<Tab>('Alerts')
  const sensorMapRef = useRef<L.Map | null>(null)

  const { data: alertData } = useApi(() => api.earlyWarning('alerts'), [])
  const { data: sensorData } = useApi(() => api.sensors(), [])

  const ad = alertData as any
  const sd = sensorData as any

  const handleSensorMapReady = useCallback((map: L.Map) => {
    sensorMapRef.current = map
    api.sensors().then((d: any) => {
      d?.sensors?.forEach((s: any) => {
        L.circleMarker([s.lat ?? 8.46, s.lng ?? -11.78], {
          radius: 7,
          fillColor: s.online ? '#729e75' : '#943d3a',
          color: s.online ? '#afd4b2' : '#c75c54',
          fillOpacity: 0.85,
          weight: 2,
        })
          .bindTooltip(`<strong>${s.name}</strong><br/>Status: ${s.online ? '🟢 Online' : '🔴 Offline'}`)
          .addTo(map)
      })
    }).catch(() => {})
  }, [])

  const FALLBACK_ALERTS = [
    { id: 1, level: 'critical', title: 'Severe Flood Warning — Bombali District', district: 'Bombali', time: '2h ago', desc: 'River levels critical. Evacuation recommended for riverside communities.' },
    { id: 2, level: 'high',     title: 'Malaria Surge Predicted — Port Loko',    district: 'Port Loko', time: '4h ago', desc: 'High vector suitability detected. Pre-position RDTs and ACTs.' },
    { id: 3, level: 'high',     title: 'Flood Risk Elevated — Koinadugu',        district: 'Koinadugu', time: '6h ago', desc: 'Soil saturation at 94%. Monitor upstream discharge.' },
    { id: 4, level: 'moderate', title: 'Air Quality Degraded — Freetown',        district: 'Western Urban', time: '9h ago', desc: 'AQI 87. Vulnerable populations advised to limit outdoor exposure.' },
    { id: 5, level: 'moderate', title: 'Heat Stress Advisory — Northern Province', district: 'Koinadugu', time: '12h ago', desc: 'WBGT above 32°C expected next 48h.' },
  ]

  const FALLBACK_FORECAST = [
    { period: 'Next 24h', flood: 0.78, malaria: 0.65, heat: 0.42, districts_alert: 4 },
    { period: 'Day 2–3',  flood: 0.82, malaria: 0.70, heat: 0.38, districts_alert: 5 },
    { period: 'Day 4–7',  flood: 0.61, malaria: 0.74, heat: 0.35, districts_alert: 3 },
    { period: '2nd Week', flood: 0.45, malaria: 0.68, heat: 0.32, districts_alert: 2 },
  ]

  const alerts = ad?.alerts ?? FALLBACK_ALERTS
  const online = sd?.online ?? 12
  const total  = sd?.total  ?? 16
  const sensors = sd?.sensors ?? []

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <h2>Early Warning Center</h2>
          <p className={styles.desc}>Live alerts, multi-hazard forecasts, and sensor network</p>
        </div>
        <div className={styles.onlinePill}>
          <span className="pulse-dot" /> {online}/{total} Sensors Online
        </div>
      </div>

      <div className={styles.kpiGrid}>
        <StatCard value={alerts.filter((a: any) => a.level === 'critical').length} label="Critical Alerts" colour="red" />
        <StatCard value={alerts.filter((a: any) => a.level === 'high').length}     label="High Alerts"     colour="orange" />
        <StatCard value={online}                                                   label="Sensors Online"  colour="green" />
        <StatCard value={total - online}                                           label="Sensors Offline" />
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        {TABS.map(t => (
          <button
            key={t}
            className={`${styles.tab} ${activeTab === t ? styles.tabActive : ''}`}
            onClick={() => setActiveTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {activeTab === 'Alerts' && (
        <div className={styles.alertsList}>
          {alerts.map((a: any) => (
            <div key={a.id} className={`${styles.alertCard} ${styles[`alert_${a.level}`]}`}>
              <div className={styles.alertLeft}>
                <RiskBadge level={a.level} />
                <div className={styles.alertTitle}>{a.title}</div>
                <div className={styles.alertDesc}>{a.desc}</div>
              </div>
              <div className={styles.alertRight}>
                <span className={styles.alertDistrict}>{a.district}</span>
                <span className={styles.alertTime}>{a.time}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'Forecast' && (
        <div className={styles.forecastGrid}>
          {FALLBACK_FORECAST.map((f, i) => (
            <div key={i} className={styles.forecastCard}>
              <div className={styles.forecastPeriod}>{f.period}</div>
              <div className={styles.forecastRow}>
                <span>Flood Risk</span>
                <div className={styles.forecastBar}>
                  <div className={styles.forecastFill} style={{ width: `${f.flood * 100}%`, background: f.flood > 0.7 ? 'var(--red)' : 'var(--orange)' }} />
                </div>
                <span className={styles.forecastVal}>{(f.flood * 100).toFixed(0)}%</span>
              </div>
              <div className={styles.forecastRow}>
                <span>Malaria Risk</span>
                <div className={styles.forecastBar}>
                  <div className={styles.forecastFill} style={{ width: `${f.malaria * 100}%`, background: f.malaria > 0.7 ? 'var(--red)' : 'var(--orange)' }} />
                </div>
                <span className={styles.forecastVal}>{(f.malaria * 100).toFixed(0)}%</span>
              </div>
              <div className={styles.forecastRow}>
                <span>Heat Stress</span>
                <div className={styles.forecastBar}>
                  <div className={styles.forecastFill} style={{ width: `${f.heat * 100}%`, background: 'var(--orange)' }} />
                </div>
                <span className={styles.forecastVal}>{(f.heat * 100).toFixed(0)}%</span>
              </div>
              <div className={styles.forecastMeta}>{f.districts_alert} districts on alert</div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'Sensors' && (
        <div className={styles.sensorGrid}>
          {(sensors.length ? sensors : Array.from({ length: 8 }, (_, i) => ({
            name: `Sensor ${i + 1}`, online: i < 6,
            readings: { temperature: (26 + i).toFixed(1), humidity: 75 + i, river_level: i < 3 ? 'Normal' : 'High', aqi: 35 + i },
            battery_pct: 90 - i * 8, signal_strength: 'Strong', last_reading: `${i + 1}h ago`,
          }))).map((s: any, i: number) => (
            <div key={i} className={`${styles.sensorCard} ${!s.online ? styles.sensorOffline : ''}`}>
              <div className={styles.sensorHeader}>
                <span className={styles.sensorName}>{s.name}</span>
                <span className={`${styles.sensorStatus} ${s.online ? styles.statusOnline : styles.statusOffline}`}>
                  {s.online ? 'ONLINE' : 'OFFLINE'}
                </span>
              </div>
              <div className={styles.sensorReadings}>
                <div className={styles.sensorReading}><span>Temp</span><strong>{s.readings?.temperature}°C</strong></div>
                <div className={styles.sensorReading}><span>Humidity</span><strong>{s.readings?.humidity}%</strong></div>
                <div className={styles.sensorReading}><span>River</span><strong>{s.readings?.river_level}</strong></div>
                <div className={styles.sensorReading}><span>AQI</span><strong>{s.readings?.aqi}</strong></div>
              </div>
              <div className={styles.sensorFooter}>
                <span>🔋 {s.battery_pct}%</span>
                <span>{s.signal_strength}</span>
                <span>{s.last_reading}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'EOC Map' && (
        <div className={styles.mapWrapper}>
          <LeafletMap onMapReady={handleSensorMapReady} style={{ height: 500 }} />
        </div>
      )}
    </div>
  )
}
