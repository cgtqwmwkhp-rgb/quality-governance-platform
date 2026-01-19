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
// Audit Tool Builder
import AuditTemplateLibrary from './pages/AuditTemplateLibrary'
import AuditTemplateBuilder from './pages/AuditTemplateBuilder'
import AuditExecution from './pages/AuditExecution'
import MobileAuditExecution from './pages/MobileAuditExecution'
import Portal from './pages/Portal'
import PortalLogin from './pages/PortalLogin'
import PortalReport from './pages/PortalReport'
import PortalTrack from './pages/PortalTrack'
import PortalSOS from './pages/PortalSOS'
import PortalHelp from './pages/PortalHelp'
import PortalIncidentForm from './pages/PortalIncidentForm'
import PortalRTAForm from './pages/PortalRTAForm'
// Enterprise Enhancement Pages
import Analytics from './pages/Analytics'
import GlobalSearch from './pages/GlobalSearch'
import UserManagement from './pages/UserManagement'
import AuditTrail from './pages/AuditTrail'
import CalendarView from './pages/CalendarView'
import Notifications from './pages/Notifications'
import ExportCenter from './pages/ExportCenter'
import ComplianceEvidence from './pages/ComplianceEvidence'
// Phase 2: Advanced Analytics & Reporting
import AdvancedAnalytics from './pages/AdvancedAnalytics'
import DashboardBuilder from './pages/DashboardBuilder'
import ReportGenerator from './pages/ReportGenerator'
// Phase 3: Workflow Automation
import WorkflowCenter from './pages/WorkflowCenter'
// Phase 4: Compliance Automation
import ComplianceAutomation from './pages/ComplianceAutomation'
import Layout from './components/Layout'
import PortalLayout from './components/PortalLayout'
import { PortalAuthProvider } from './contexts/PortalAuthContext'

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
        {/* Portal Login - Public */}
        <Route 
          path="/portal/login" 
          element={
            <PortalAuthProvider>
              <PortalLogin />
            </PortalAuthProvider>
          } 
        />
        
        {/* Protected Employee Portal Routes - Requires SSO */}
        <Route 
          path="/portal"
          element={
            <PortalAuthProvider>
              <PortalLayout />
            </PortalAuthProvider>
          }
        >
          {/* Level 1: Portal Home */}
          <Route index element={<Portal />} />
          
          {/* Level 2: Report Type Selection */}
          <Route path="report" element={<PortalReport />} />
          
          {/* Level 3: Report Forms */}
          <Route path="report/incident" element={<PortalIncidentForm />} />
          <Route path="report/near-miss" element={<PortalIncidentForm />} />
          <Route path="report/complaint" element={<PortalIncidentForm />} />
          <Route path="report/rta" element={<PortalRTAForm />} />
          
          {/* Other Portal Pages */}
          <Route path="track" element={<PortalTrack />} />
          <Route path="track/:referenceNumber" element={<PortalTrack />} />
          <Route path="sos" element={<PortalSOS />} />
          <Route path="help" element={<PortalHelp />} />
        </Route>
        
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
          <Route path="audit-templates" element={<AuditTemplateLibrary />} />
          <Route path="audit-templates/new" element={<AuditTemplateBuilder />} />
          <Route path="audit-templates/:templateId/edit" element={<AuditTemplateBuilder />} />
          <Route path="audits/:auditId/execute" element={<AuditExecution />} />
          <Route path="audits/:auditId/mobile" element={<MobileAuditExecution />} />
          <Route path="investigations" element={<Investigations />} />
          <Route path="standards" element={<Standards />} />
          <Route path="actions" element={<Actions />} />
          <Route path="documents" element={<Documents />} />
          {/* Enterprise Enhancement Routes */}
          <Route path="analytics" element={<Analytics />} />
          <Route path="analytics/advanced" element={<AdvancedAnalytics />} />
          <Route path="analytics/dashboards" element={<DashboardBuilder />} />
          <Route path="analytics/reports" element={<ReportGenerator />} />
          <Route path="search" element={<GlobalSearch />} />
          <Route path="users" element={<UserManagement />} />
          <Route path="audit-trail" element={<AuditTrail />} />
          <Route path="calendar" element={<CalendarView />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="exports" element={<ExportCenter />} />
          <Route path="compliance" element={<ComplianceEvidence />} />
          {/* Phase 3: Workflow Automation */}
          <Route path="workflows" element={<WorkflowCenter />} />
          {/* Phase 4: Compliance Automation */}
          <Route path="compliance-automation" element={<ComplianceAutomation />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
