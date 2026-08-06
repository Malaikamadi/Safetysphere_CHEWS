import { useCallback } from 'react'
import L from 'leaflet'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import LeafletMap from '../components/map/LeafletMap'
import StatCard from '../components/ui/StatCard'
import RiskBadge from '../components/ui/RiskBadge'
import styles from './District.module.css'

export default function District() {
  const { district } = useAuth()
  const { data } = useApi(() => api.situationRoom(), [])
  const sr = data as any

  const handleMapReady = useCallback((map: L.Map) => {
    // Zoom to district if available
    map.setView([8.46, -11.78], 8)
  }, [])

  const FACILITIES = [
    { name: 'District Hospital', beds: 120, staff: 45, readiness: 72, malaria: 'high' },
    { name: 'Community Health Centre', beds: 30, staff: 12, readiness: 55, malaria: 'high' },
    { name: 'Primary Health Unit A', beds: 10, staff: 4, readiness: 41, malaria: 'moderate' },
    { name: 'Primary Health Unit B', beds: 8, staff: 3, readiness: 38, malaria: 'moderate' },
  ]

  return (
    <div className={styles.page}>
      <div>
        <h2>District Dashboard</h2>
        <p className={styles.desc}>{district ?? 'District'} · Health Intelligence Overview</p>
      </div>

      <div className={styles.kpiGrid}>
        <StatCard value="0.72"   label="District Risk Score" colour="red"    />
        <StatCard value="4"      label="Health Facilities"   colour="blue"   />
        <StatCard value="210K"   label="Population Served"   colour="green"  />
        <StatCard value="High"   label="Alert Status"        colour="red"    />
      </div>

      <div className={styles.twoCol}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>District Risk Map</h3>
          <LeafletMap onMapReady={handleMapReady} zoom={8} style={{ height: 340 }} />
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Facility Overview</h3>
          <div className={styles.facilityList}>
            {FACILITIES.map(f => (
              <div key={f.name} className={styles.facilityItem}>
                <div className={styles.facilityTop}>
                  <span className={styles.facilityName}>{f.name}</span>
                  <RiskBadge level={f.malaria} />
                </div>
                <div className={styles.facilityStats}>
                  <span>Beds: {f.beds}</span>
                  <span>Staff: {f.staff}</span>
                  <span>Readiness: {f.readiness}%</span>
                </div>
                <div className={styles.facilityBar}>
                  <div style={{ width: `${f.readiness}%`, background: f.readiness < 50 ? 'var(--red)' : f.readiness < 70 ? 'var(--orange)' : 'var(--green)' }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Recent CHW Reports</h3>
        <div className={styles.reportsList}>
          {[
            { reporter: 'CHW Fatmata K.', location: 'Mange Village', report: 'High fever cases in 3 households — suspected malaria', time: '2h ago', verified: true },
            { reporter: 'CHW Ibrahim S.', location: 'Rokel Town', report: 'Flooding near the clinic — access road blocked', time: '5h ago', verified: false },
            { reporter: 'CHW Aminata D.', location: 'Gbonkolenken', report: 'RDT stock depleted. 12 patients awaiting testing', time: '8h ago', verified: true },
          ].map((r, i) => (
            <div key={i} className={styles.reportItem}>
              <div className={styles.reportHeader}>
                <span className={styles.reporterName}>{r.reporter}</span>
                <span className={styles.reportLocation}>{r.location}</span>
                <span className={styles.reportTime}>{r.time}</span>
                {r.verified && <span className={styles.verified}>✓ Verified</span>}
              </div>
              <p className={styles.reportText}>{r.report}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
