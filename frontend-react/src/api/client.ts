// ── Centralised API client for CHEWS
// All fetch() calls go through here. API_BASE from .env

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

// ── System ─────────────────────────────────────────────────────────────────
export const api = {
  health: () => request<Record<string, unknown>>('/health'),

  // ── Prediction ────────────────────────────────────────────────────────────
  predict: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/predict', { method: 'POST', body: JSON.stringify(payload) }),

  ask: (payload: { question: string; risk_score?: number }) =>
    request<{ question: string; answer: string }>('/ask', { method: 'POST', body: JSON.stringify(payload) }),

  // ── Situation Room ─────────────────────────────────────────────────────────
  situationRoom: () => request<Record<string, unknown>>('/situation-room'),
  situationRoomMap: () => request<Record<string, unknown>>('/situation-room/map-data'),
  situationRoomTimeline: (dayOffset: number) =>
    request<Record<string, unknown>>(`/situation-room/timeline/${dayOffset}`),
  situationRoomAIExplain: (hazard: string) =>
    request<Record<string, unknown>>(`/situation-room/ai-explain/${hazard}`),
  situationRoomScenario: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/situation-room/scenario', { method: 'POST', body: JSON.stringify(payload) }),
  communityReports: () => request<Record<string, unknown>>('/situation-room/community-reports'),
  sensors: () => request<Record<string, unknown>>('/situation-room/sensors'),
  digitalTwins: () => request<Record<string, unknown>>('/situation-room/digital-twins'),
  decisionSupport: () => request<Record<string, unknown>>('/situation-room/decision-support'),

  // ── Strategic ─────────────────────────────────────────────────────────────
  strategicPredict: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/strategic/predict', { method: 'POST', body: JSON.stringify(payload) }),
  floodDashboard: () => request<Record<string, unknown>>('/strategic/flood-dashboard'),
  floodForecast: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/strategic/flood-forecast', { method: 'POST', body: JSON.stringify(payload) }),
  floodZoneForecast: (id: string) =>
    request<Record<string, unknown>>(`/strategic/flood-zone/${id}/forecast?hours=24`),

  // ── Early Warning ─────────────────────────────────────────────────────────
  earlyWarning: (path: string, payload?: Record<string, unknown>) =>
    payload
      ? request<Record<string, unknown>>(`/early-warning/${path}`, { method: 'POST', body: JSON.stringify(payload) })
      : request<Record<string, unknown>>(`/early-warning/${path}`),

  // ── Healthcare ───────────────────────────────────────────────────────────
  healthcareForecast: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/healthcare/forecast', { method: 'POST', body: JSON.stringify(payload) }),
  anomalyDetect: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/healthcare/anomaly-detect', { method: 'POST', body: JSON.stringify(payload) }),
  surgePlan: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/healthcare/surge-plan', { method: 'POST', body: JSON.stringify(payload) }),
  malariaPredict: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/healthcare/ml/malaria-predict', { method: 'POST', body: JSON.stringify(payload) }),
  readinessPredict: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/healthcare/ml/readiness-predict', { method: 'POST', body: JSON.stringify(payload) }),
  communityFlood: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/healthcare/ml/community-flood', { method: 'POST', body: JSON.stringify(payload) }),

  // ── Point of Care ─────────────────────────────────────────────────────────
  triage: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/poc/triage', { method: 'POST', body: JSON.stringify(payload) }),
  pocAsk: (payload: Record<string, unknown>) =>
    request<{ answer: string }>('/poc/ask', { method: 'POST', body: JSON.stringify(payload) }),
}
