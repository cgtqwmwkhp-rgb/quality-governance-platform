import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Incidents from './pages/Incidents'
import RTAs from './pages/RTAs'
import Complaints from './pages/Complaints'
import Policies from './pages/Policies'
import Risks from './pages/Risks'
import Audits from './pages/Audits'
import Investigations from './pages/Investigations'
import Standards from './pages/Standards'
import Actions from './pages/Actions'
import Documents from './pages/Documents'
import Portal from './pages/Portal'
import PortalReport from './pages/PortalReport'
import PortalTrack from './pages/PortalTrack'
import Layout from './components/Layout'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    setIsAuthenticated(!!token)
    setIsLoading(false)
  }, [])

  const handleLogin = (token: string) => {
    localStorage.setItem('access_token', token)
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    setIsAuthenticated(false)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-emerald-500/20 border-t-emerald-500"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Public Employee Portal Routes - No Auth Required */}
        <Route path="/portal" element={<Portal />} />
        <Route path="/portal/report" element={<PortalReport />} />
        <Route path="/portal/track" element={<PortalTrack />} />
        <Route path="/portal/track/:referenceNumber" element={<PortalTrack />} />
        
        {/* Auth Routes */}
        <Route
          path="/login"
          element={
            isAuthenticated ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <Login onLogin={handleLogin} />
            )
          }
        />
        
        {/* Protected Admin Routes */}
        <Route
          path="/"
          element={
            isAuthenticated ? (
              <Layout onLogout={handleLogout} />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="rtas" element={<RTAs />} />
          <Route path="complaints" element={<Complaints />} />
          <Route path="policies" element={<Policies />} />
          <Route path="risks" element={<Risks />} />
          <Route path="audits" element={<Audits />} />
          <Route path="investigations" element={<Investigations />} />
          <Route path="standards" element={<Standards />} />
          <Route path="actions" element={<Actions />} />
          <Route path="documents" element={<Documents />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
