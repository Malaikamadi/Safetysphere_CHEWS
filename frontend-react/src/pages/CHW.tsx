import { useState } from 'react'
import { api } from '../api/client'
import StatCard from '../components/ui/StatCard'
import styles from './CHW.module.css'

export default function CHW() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  async function sendQuestion() {
    if (!question.trim()) return
    setChatLoading(true)
    try {
      const res = await api.pocAsk({ question })
      setAnswer(res.answer)
    } catch { setAnswer('Service unavailable. Please try again later.') }
    setChatLoading(false)
  }

  const ALERTS = [
    { level: 'critical', title: 'Flood Warning', desc: 'Avoid low-lying areas. Evacuate if near rivers.', time: '1h ago' },
    { level: 'high',     title: 'Malaria Alert', desc: 'High malaria risk in your area. Ensure nets are used.', time: '3h ago' },
    { level: 'moderate', title: 'Heat Advisory', desc: 'High temperatures expected. Ensure hydration.', time: '6h ago' },
  ]

  return (
    <div className={styles.page}>
      <div>
        <h2>Community Health Worker</h2>
        <p className={styles.desc}>Field alerts, patient triage, and health assistant</p>
      </div>

      <div className={styles.kpiGrid}>
        <StatCard value="3"  label="Active Alerts"    colour="red"    />
        <StatCard value="12" label="Reports This Week" colour="blue"   />
        <StatCard value="8"  label="Patients Triaged"  colour="green"  />
        <StatCard value="High" label="Area Risk Level" colour="red"    />
      </div>

      <div className={styles.twoCol}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Active Alerts</h3>
          <div className={styles.alertsList}>
            {ALERTS.map((a, i) => (
              <div key={i} className={`${styles.alertItem} ${styles[`alert_${a.level}`]}`}>
                <div className={styles.alertLevel}>{a.level}</div>
                <div>
                  <div className={styles.alertTitle}>{a.title}</div>
                  <div className={styles.alertDesc}>{a.desc}</div>
                  <div className={styles.alertTime}>{a.time}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Health Assistant</h3>
          <div className={styles.chatBox}>
            {answer && (
              <div className={styles.chatAnswer}>
                <div className={styles.chatLabel}>CHEWS AI</div>
                <p>{answer}</p>
              </div>
            )}
          </div>
          <div className={styles.chatInput}>
            <input
              type="text"
              className={styles.input}
              placeholder="Ask about malaria, symptoms, prevention…"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendQuestion()}
            />
            <button className={styles.sendBtn} onClick={sendQuestion} disabled={chatLoading}>
              {chatLoading ? '…' : 'Ask'}
            </button>
          </div>
          <div className={styles.quickTags}>
            {['What is malaria?', 'How to prevent?', 'Symptoms', 'Children', 'Pregnant women'].map(q => (
              <button key={q} className={styles.quickTag} onClick={() => { setQuestion(q); }}>
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
