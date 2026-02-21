import React, { useState, useEffect, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import PortalLayout from './components/PortalLayout'
import PageErrorBoundary from './components/PageErrorBoundary'
import { PortalAuthProvider } from './contexts/PortalAuthContext'

function LoadingFallback() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary/20 border-t-primary" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  )
}

// Code-split all page components for faster initial load
const Login = React.lazy(() => import('./pages/Login'))
const Dashboard = React.lazy(() => import('./pages/Dashboard'))
const Incidents = React.lazy(() => import('./pages/Incidents'))
const IncidentDetail = React.lazy(() => import('./pages/IncidentDetail'))
const RTAs = React.lazy(() => import('./pages/RTAs'))
const RTADetail = React.lazy(() => import('./pages/RTADetail'))
const Complaints = React.lazy(() => import('./pages/Complaints'))
const ComplaintDetail = React.lazy(() => import('./pages/ComplaintDetail'))
const Policies = React.lazy(() => import('./pages/Policies'))
const Audits = React.lazy(() => import('./pages/Audits'))
const Investigations = React.lazy(() => import('./pages/Investigations'))
const InvestigationDetail = React.lazy(() => import('./pages/InvestigationDetail'))
const Standards = React.lazy(() => import('./pages/Standards'))
const Actions = React.lazy(() => import('./pages/Actions'))
const Documents = React.lazy(() => import('./pages/Documents'))
const AuditTemplateLibrary = React.lazy(() => import('./pages/AuditTemplateLibrary'))
const AuditTemplateBuilder = React.lazy(() => import('./pages/AuditTemplateBuilder'))
const AuditExecution = React.lazy(() => import('./pages/AuditExecution'))
const MobileAuditExecution = React.lazy(() => import('./pages/MobileAuditExecution'))
const Portal = React.lazy(() => import('./pages/Portal'))
const PortalLogin = React.lazy(() => import('./pages/PortalLogin'))
const ForgotPassword = React.lazy(() => import('./pages/ForgotPassword'))
const ResetPassword = React.lazy(() => import('./pages/ResetPassword'))
const PortalReport = React.lazy(() => import('./pages/PortalReport'))
const PortalTrack = React.lazy(() => import('./pages/PortalTrack'))
const PortalHelp = React.lazy(() => import('./pages/PortalHelp'))
const PortalIncidentForm = React.lazy(() => import('./pages/PortalIncidentForm'))
const PortalRTAForm = React.lazy(() => import('./pages/PortalRTAForm'))
const PortalNearMissForm = React.lazy(() => import('./pages/PortalNearMissForm'))
const PortalDynamicForm = React.lazy(() => import('./pages/PortalDynamicForm'))
const Analytics = React.lazy(() => import('./pages/Analytics'))
const GlobalSearch = React.lazy(() => import('./pages/GlobalSearch'))
const UserManagement = React.lazy(() => import('./pages/UserManagement'))
const AuditTrail = React.lazy(() => import('./pages/AuditTrail'))
const CalendarView = React.lazy(() => import('./pages/CalendarView'))
const Notifications = React.lazy(() => import('./pages/Notifications'))
const ExportCenter = React.lazy(() => import('./pages/ExportCenter'))
const ComplianceEvidence = React.lazy(() => import('./pages/ComplianceEvidence'))
const AdvancedAnalytics = React.lazy(() => import('./pages/AdvancedAnalytics'))
const DashboardBuilder = React.lazy(() => import('./pages/DashboardBuilder'))
const ReportGenerator = React.lazy(() => import('./pages/ReportGenerator'))
const WorkflowCenter = React.lazy(() => import('./pages/WorkflowCenter'))
const ComplianceAutomation = React.lazy(() => import('./pages/ComplianceAutomation'))
const RiskRegister = React.lazy(() => import('./pages/RiskRegister'))
const IMSDashboard = React.lazy(() => import('./pages/IMSDashboard'))
const AIIntelligence = React.lazy(() => import('./pages/AIIntelligence'))
const UVDBAudits = React.lazy(() => import('./pages/UVDBAudits'))
const PlanetMark = React.lazy(() => import('./pages/PlanetMark'))
const DigitalSignatures = React.lazy(() => import('./pages/DigitalSignatures'))
const AdminDashboard = React.lazy(() => import('./pages/admin/AdminDashboard'))
const FormsList = React.lazy(() => import('./pages/admin/FormsList'))
const FormBuilder = React.lazy(() => import('./pages/admin/FormBuilder'))
const ContractsManagement = React.lazy(() => import('./pages/admin/ContractsManagement'))
const SystemSettings = React.lazy(() => import('./pages/admin/SystemSettings'))

import { API_BASE_URL } from './config/apiBase'

// Declare build version globals injected by Vite
declare const __BUILD_VERSION__: string
declare const __BUILD_TIME__: string

// Log versions on app startup for UAT debugging
function logVersionInfo() {
  const frontendVersion = typeof __BUILD_VERSION__ !== 'undefined' ? __BUILD_VERSION__ : 'dev'
  const frontendBuildTime = typeof __BUILD_TIME__ !== 'undefined' ? __BUILD_TIME__ : 'local'
  
  console.group('[QGP] Application Version Info')
  console.log('Frontend SHA:', frontendVersion)
  console.log('Frontend Build:', frontendBuildTime)
  console.log('API Base URL:', API_BASE_URL)
  
  // Fetch backend version using the correct API base URL
  fetch(`${API_BASE_URL}/api/v1/meta/version`, { method: 'GET' })
    .then(res => res.ok ? res.json() : Promise.reject(res.status))
    .then(data => {
      console.log('Backend SHA:', data.build_sha || 'unknown')
      console.log('Backend Build:', data.build_time || 'unknown')
      console.log('Backend Environment:', data.environment || 'unknown')
      console.groupEnd()
    })
    .catch(err => {
      console.log('Backend Version: unavailable (', err, ')')
      console.groupEnd()
    })
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    setIsAuthenticated(!!token)
    setIsLoading(false)
    
    // Log version info on app mount (for UAT debugging)
    logVersionInfo()
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
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary/20 border-t-primary"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-8 h-8 rounded-lg gradient-brand"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <PageErrorBoundary>
      <Suspense fallback={<LoadingFallback />}>
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
          
          {/* Level 3: Report Forms - Pass formType explicitly to avoid URL parsing issues */}
          <Route path="report/incident" element={<PortalDynamicForm key="incident" formType="incident" />} />
          <Route path="report/near-miss" element={<PortalDynamicForm key="near-miss" formType="near-miss" />} />
          <Route path="report/complaint" element={<PortalDynamicForm key="complaint" formType="complaint" />} />
          <Route path="report/rta" element={<PortalRTAForm />} />
          
          {/* Legacy static forms (fallback) */}
          <Route path="report/incident-legacy" element={<PortalIncidentForm />} />
          <Route path="report/near-miss-static" element={<PortalNearMissForm />} />
          
          {/* Other Portal Pages */}
          <Route path="track" element={<PortalTrack />} />
          <Route path="track/:referenceNumber" element={<PortalTrack />} />
          {/* Emergency SOS removed - use phone calls for emergencies */}
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
        
        {/* Password Reset Routes - Public */}
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        
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
          <Route path="incidents/:id" element={<IncidentDetail />} />
          <Route path="rtas" element={<RTAs />} />
          <Route path="rtas/:id" element={<RTADetail />} />
          <Route path="complaints" element={<Complaints />} />
          <Route path="complaints/:id" element={<ComplaintDetail />} />
          <Route path="policies" element={<Policies />} />
          <Route path="risks" element={<Navigate to="/risk-register" replace />} />
          <Route path="audits" element={<Audits />} />
          <Route path="audit-templates" element={<AuditTemplateLibrary />} />
          <Route path="audit-templates/new" element={<AuditTemplateBuilder />} />
          <Route path="audit-templates/:templateId/edit" element={<AuditTemplateBuilder />} />
          <Route path="audits/:auditId/execute" element={<AuditExecution />} />
          <Route path="audits/:auditId/mobile" element={<MobileAuditExecution />} />
          <Route path="investigations" element={<Investigations />} />
          <Route path="investigations/:id" element={<InvestigationDetail />} />
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
          {/* Tier 1: Enterprise Risk Register & IMS Unification */}
          <Route path="risk-register" element={<RiskRegister />} />
          <Route path="ims" element={<IMSDashboard />} />
          {/* Tier 2: AI Intelligence */}
          <Route path="ai-intelligence" element={<AIIntelligence />} />
          {/* UVDB Achilles Verify */}
          <Route path="uvdb" element={<UVDBAudits />} />
          {/* Planet Mark Carbon Management */}
          <Route path="planet-mark" element={<PlanetMark />} />
          {/* Tier 2: Digital Signatures */}
          <Route path="signatures" element={<DigitalSignatures />} />
          
          {/* Admin Configuration Routes */}
          <Route path="admin" element={<AdminDashboard />} />
          <Route path="admin/forms" element={<FormsList />} />
          <Route path="admin/forms/new" element={<FormBuilder />} />
          <Route path="admin/forms/:templateId" element={<FormBuilder />} />
          <Route path="admin/contracts" element={<ContractsManagement />} />
          <Route path="admin/settings" element={<SystemSettings />} />
        </Route>
      </Routes>
      </Suspense>
      </PageErrorBoundary>
    </BrowserRouter>
  )
}

export default App
