import { Navigate, Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { useAuth } from '../../context/AuthContext'

interface Props {
  title?: string
  subtitle?: string
}

/** Wraps authenticated pages with sidebar + topbar. Redirects to /login if not authed. */
export default function AppLayout({ title, subtitle }: Props) {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) return <Navigate to="/login" replace />

  return (
    <>
      <div className="bg-animation" aria-hidden="true">
        <div className="bg-orb bg-orb--1" />
        <div className="bg-orb bg-orb--2" />
        <div className="bg-orb bg-orb--3" />
        <div className="bg-orb bg-orb--4" />
      </div>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Topbar title={title} subtitle={subtitle} />
          <div className="page-content">
            <Outlet />
          </div>
        </main>
      </div>
    </>
  )
}
