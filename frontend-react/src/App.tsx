import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import AppLayout from './components/layout/AppLayout'

// Pages
import Login from './pages/Login'
import SituationRoom from './pages/SituationRoom'
import EarlyWarning from './pages/EarlyWarning'
import Strategic from './pages/Strategic'
import Healthcare from './pages/Healthcare'
import District from './pages/District'
import CHW from './pages/CHW'
import Partner from './pages/Partner'
import PointOfCare from './pages/PointOfCare'
import AIModels from './pages/AIModels'

function RootRedirect() {
  const { role, roleConfig } = useAuth()
  if (!role || !roleConfig) return <Navigate to="/login" replace />
  return <Navigate to={roleConfig.homePath} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />

          {/* Protected — all share AppLayout */}
          <Route element={<AppLayout title="CHEWS" subtitle="Climate & Health Early Warning System" />}>
            <Route path="/" element={<RootRedirect />} />
            <Route path="/situation-room" element={<SituationRoom />} />
            <Route path="/early-warning" element={<EarlyWarning />} />
            <Route path="/strategic" element={<Strategic />} />
            <Route path="/healthcare" element={<Healthcare />} />
            <Route path="/district" element={<District />} />
            <Route path="/chw" element={<CHW />} />
            <Route path="/partner" element={<Partner />} />
            <Route path="/poc" element={<PointOfCare />} />
            <Route path="/ai-models" element={<AIModels />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
