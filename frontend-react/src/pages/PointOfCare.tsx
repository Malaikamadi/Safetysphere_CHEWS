import { useState } from 'react'
import { api } from '../api/client'
import RiskBadge from '../components/ui/RiskBadge'
import styles from './PointOfCare.module.css'

export default function PointOfCare() {
  const [form, setForm] = useState({
    patient_age: 25, temperature: 38.2, symptoms: 'fever,headache',
    malaria_rdt: 'positive', duration_days: 3, location_type: 'rural'
  })
  const [triageResult, setTriageResult] = useState<any>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)

  async function runTriage() {
    setLoading(true)
    try {
      const res = await api.triage(form as any)
      setTriageResult(res)
    } catch { setTriageResult({ error: 'Backend offline' }) }
    setLoading(false)
  }

  async function sendQuestion() {
    if (!question.trim()) return
    setChatLoading(true)
    try {
      const res = await api.pocAsk({ question, risk_score: triageResult?.risk_score })
      setAnswer(res.answer)
    } catch { setAnswer('Service unavailable.') }
    setChatLoading(false)
  }

  return (
    <div className={styles.page}>
      <div>
        <h2>Point of Care Triage</h2>
        <p className={styles.desc}>AI-assisted patient triage and clinical decision support</p>
      </div>

      <div className={styles.twoCol}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Patient Triage</h3>
          <div className={styles.formGrid}>
            {[
              { label: 'Patient Age', key: 'patient_age', type: 'number' },
              { label: 'Temperature (°C)', key: 'temperature', type: 'number' },
              { label: 'Duration (days)', key: 'duration_days', type: 'number' },
            ].map(f => (
              <label key={f.key} className={styles.formField}>
                <span>{f.label}</span>
                <input type={f.type} value={(form as any)[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: +e.target.value }))} className={styles.input} />
              </label>
            ))}
            <label className={styles.formField}>
              <span>Malaria RDT</span>
              <select className={styles.input} value={form.malaria_rdt} onChange={e => setForm(p => ({ ...p, malaria_rdt: e.target.value }))}>
                <option value="positive">Positive</option>
                <option value="negative">Negative</option>
                <option value="pending">Pending</option>
              </select>
            </label>
            <label className={styles.formField} style={{ gridColumn: '1 / -1' }}>
              <span>Symptoms (comma separated)</span>
              <input type="text" value={form.symptoms} onChange={e => setForm(p => ({ ...p, symptoms: e.target.value }))} className={styles.input} />
            </label>
          </div>
          <button className={styles.runBtn} onClick={runTriage} disabled={loading}>
            {loading ? 'Triaging…' : 'Run AI Triage'}
          </button>

          {triageResult && !triageResult.error && (
            <div className={styles.triageResult}>
              <div className={styles.triageTop}>
                <span>Priority: </span>
                <RiskBadge level={triageResult.priority ?? triageResult.risk_level ?? 'moderate'} />
                <span className={styles.triageScore}>Score: {(triageResult.risk_score ?? 0).toFixed(2)}</span>
              </div>
              {triageResult.recommendation && (
                <div className={styles.recommendation}>{triageResult.recommendation}</div>
              )}
              {triageResult.actions && (
                <ul className={styles.actionList}>
                  {triageResult.actions.map((a: string, i: number) => <li key={i}>{a}</li>)}
                </ul>
              )}
            </div>
          )}
          {triageResult?.error && <p className={styles.errorMsg}>{triageResult.error}</p>}
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Clinical Health Assistant</h3>
          <div className={styles.chatMessages}>
            {answer && (
              <div className={styles.chatAnswer}>
                <div className={styles.chatLabel}>CHEWS AI</div>
                <p>{answer}</p>
              </div>
            )}
          </div>
          <div className={styles.chatInputRow}>
            <input
              className={styles.input}
              type="text"
              placeholder="Clinical question…"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendQuestion()}
            />
            <button className={styles.sendBtn} onClick={sendQuestion} disabled={chatLoading}>
              {chatLoading ? '…' : 'Ask'}
            </button>
          </div>
          <div className={styles.quickTags}>
            {['Malaria dosage', 'Referral criteria', 'Cholera protocol', 'Paediatric dosing', 'Fever management'].map(q => (
              <button key={q} className={styles.quickTag} onClick={() => setQuestion(q)}>{q}</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
