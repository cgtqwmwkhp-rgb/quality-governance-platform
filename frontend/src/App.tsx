import React, { useState, useEffect, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import PortalLayout from './components/PortalLayout'
import ErrorBoundary from './components/ErrorBoundary'
import PageErrorBoundary from './components/PageErrorBoundary'
import { PortalAuthProvider } from './contexts/PortalAuthContext'
import { useOnlineStatus } from './hooks/useOnlineStatus'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

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

function RouteFallback({ route }: { route: string }) {
  return (
    <div className="flex items-center justify-center min-h-[60vh] p-8">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
        <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-gray-900 mb-2">{route} failed to load</h2>
        <p className="text-sm text-gray-500 mb-4">An unexpected error occurred on this page.</p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
          >
            Reload Page
          </button>
          <button
            onClick={() => window.location.href = '/dashboard'}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 text-sm font-medium"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    </div>
  )
}

function App() {
  useOnlineStatus()

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
    <QueryClientProvider client={queryClient}>
    <ErrorBoundary>
    <BrowserRouter>
      <PageErrorBoundary>
      <Suspense fallback={<LoadingFallback />}>
      <Routes>
        {/* Portal Login - Public */}
        <Route 
          path="/portal/login" 
          element={
            <ErrorBoundary fallback={<RouteFallback route="Portal Login" />}>
              <PortalAuthProvider>
                <PortalLogin />
              </PortalAuthProvider>
            </ErrorBoundary>
          } 
        />
        
        {/* Protected Employee Portal Routes - Requires SSO */}
        <Route 
          path="/portal"
          element={
            <ErrorBoundary fallback={<RouteFallback route="Employee Portal" />}>
              <PortalAuthProvider>
                <PortalLayout />
              </PortalAuthProvider>
            </ErrorBoundary>
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
              <ErrorBoundary fallback={<RouteFallback route="Login" />}>
                <Login onLogin={handleLogin} />
              </ErrorBoundary>
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
          <Route path="dashboard" element={<ErrorBoundary fallback={<RouteFallback route="Dashboard" />}><Dashboard /></ErrorBoundary>} />
          <Route path="incidents" element={<ErrorBoundary fallback={<RouteFallback route="Incidents" />}><Incidents /></ErrorBoundary>} />
          <Route path="incidents/:id" element={<ErrorBoundary fallback={<RouteFallback route="Incident Detail" />}><IncidentDetail /></ErrorBoundary>} />
          <Route path="rtas" element={<ErrorBoundary fallback={<RouteFallback route="RTAs" />}><RTAs /></ErrorBoundary>} />
          <Route path="rtas/:id" element={<ErrorBoundary fallback={<RouteFallback route="RTA Detail" />}><RTADetail /></ErrorBoundary>} />
          <Route path="complaints" element={<ErrorBoundary fallback={<RouteFallback route="Complaints" />}><Complaints /></ErrorBoundary>} />
          <Route path="complaints/:id" element={<ErrorBoundary fallback={<RouteFallback route="Complaint Detail" />}><ComplaintDetail /></ErrorBoundary>} />
          <Route path="policies" element={<ErrorBoundary fallback={<RouteFallback route="Policies" />}><Policies /></ErrorBoundary>} />
          <Route path="risks" element={<Navigate to="/risk-register" replace />} />
          <Route path="audits" element={<ErrorBoundary fallback={<RouteFallback route="Audits" />}><Audits /></ErrorBoundary>} />
          <Route path="audit-templates" element={<ErrorBoundary fallback={<RouteFallback route="Audit Templates" />}><AuditTemplateLibrary /></ErrorBoundary>} />
          <Route path="audit-templates/new" element={<ErrorBoundary fallback={<RouteFallback route="Audit Template Builder" />}><AuditTemplateBuilder /></ErrorBoundary>} />
          <Route path="audit-templates/:templateId/edit" element={<ErrorBoundary fallback={<RouteFallback route="Audit Template Builder" />}><AuditTemplateBuilder /></ErrorBoundary>} />
          <Route path="audits/:auditId/execute" element={<ErrorBoundary fallback={<RouteFallback route="Audit Execution" />}><AuditExecution /></ErrorBoundary>} />
          <Route path="audits/:auditId/mobile" element={<ErrorBoundary fallback={<RouteFallback route="Mobile Audit" />}><MobileAuditExecution /></ErrorBoundary>} />
          <Route path="investigations" element={<ErrorBoundary fallback={<RouteFallback route="Investigations" />}><Investigations /></ErrorBoundary>} />
          <Route path="investigations/:id" element={<ErrorBoundary fallback={<RouteFallback route="Investigation Detail" />}><InvestigationDetail /></ErrorBoundary>} />
          <Route path="standards" element={<ErrorBoundary fallback={<RouteFallback route="Standards" />}><Standards /></ErrorBoundary>} />
          <Route path="actions" element={<ErrorBoundary fallback={<RouteFallback route="Actions" />}><Actions /></ErrorBoundary>} />
          <Route path="documents" element={<ErrorBoundary fallback={<RouteFallback route="Documents" />}><Documents /></ErrorBoundary>} />
          {/* Enterprise Enhancement Routes */}
          <Route path="analytics" element={<ErrorBoundary fallback={<RouteFallback route="Analytics" />}><Analytics /></ErrorBoundary>} />
          <Route path="analytics/advanced" element={<ErrorBoundary fallback={<RouteFallback route="Advanced Analytics" />}><AdvancedAnalytics /></ErrorBoundary>} />
          <Route path="analytics/dashboards" element={<ErrorBoundary fallback={<RouteFallback route="Dashboard Builder" />}><DashboardBuilder /></ErrorBoundary>} />
          <Route path="analytics/reports" element={<ErrorBoundary fallback={<RouteFallback route="Report Generator" />}><ReportGenerator /></ErrorBoundary>} />
          <Route path="search" element={<ErrorBoundary fallback={<RouteFallback route="Search" />}><GlobalSearch /></ErrorBoundary>} />
          <Route path="users" element={<ErrorBoundary fallback={<RouteFallback route="User Management" />}><UserManagement /></ErrorBoundary>} />
          <Route path="audit-trail" element={<ErrorBoundary fallback={<RouteFallback route="Audit Trail" />}><AuditTrail /></ErrorBoundary>} />
          <Route path="calendar" element={<ErrorBoundary fallback={<RouteFallback route="Calendar" />}><CalendarView /></ErrorBoundary>} />
          <Route path="notifications" element={<ErrorBoundary fallback={<RouteFallback route="Notifications" />}><Notifications /></ErrorBoundary>} />
          <Route path="exports" element={<ErrorBoundary fallback={<RouteFallback route="Export Center" />}><ExportCenter /></ErrorBoundary>} />
          <Route path="compliance" element={<ErrorBoundary fallback={<RouteFallback route="Compliance" />}><ComplianceEvidence /></ErrorBoundary>} />
          {/* Phase 3: Workflow Automation */}
          <Route path="workflows" element={<ErrorBoundary fallback={<RouteFallback route="Workflows" />}><WorkflowCenter /></ErrorBoundary>} />
          {/* Phase 4: Compliance Automation */}
          <Route path="compliance-automation" element={<ErrorBoundary fallback={<RouteFallback route="Compliance Automation" />}><ComplianceAutomation /></ErrorBoundary>} />
          {/* Tier 1: Enterprise Risk Register & IMS Unification */}
          <Route path="risk-register" element={<ErrorBoundary fallback={<RouteFallback route="Risk Register" />}><RiskRegister /></ErrorBoundary>} />
          <Route path="ims" element={<ErrorBoundary fallback={<RouteFallback route="IMS Dashboard" />}><IMSDashboard /></ErrorBoundary>} />
          {/* Tier 2: AI Intelligence */}
          <Route path="ai-intelligence" element={<ErrorBoundary fallback={<RouteFallback route="AI Intelligence" />}><AIIntelligence /></ErrorBoundary>} />
          {/* UVDB Achilles Verify */}
          <Route path="uvdb" element={<ErrorBoundary fallback={<RouteFallback route="UVDB Audits" />}><UVDBAudits /></ErrorBoundary>} />
          {/* Planet Mark Carbon Management */}
          <Route path="planet-mark" element={<ErrorBoundary fallback={<RouteFallback route="Planet Mark" />}><PlanetMark /></ErrorBoundary>} />
          {/* Tier 2: Digital Signatures */}
          <Route path="signatures" element={<ErrorBoundary fallback={<RouteFallback route="Digital Signatures" />}><DigitalSignatures /></ErrorBoundary>} />
          
          {/* Admin Configuration Routes */}
          <Route path="admin" element={<ErrorBoundary fallback={<RouteFallback route="Admin" />}><AdminDashboard /></ErrorBoundary>} />
          <Route path="admin/forms" element={<ErrorBoundary fallback={<RouteFallback route="Forms" />}><FormsList /></ErrorBoundary>} />
          <Route path="admin/forms/new" element={<ErrorBoundary fallback={<RouteFallback route="Form Builder" />}><FormBuilder /></ErrorBoundary>} />
          <Route path="admin/forms/:templateId" element={<ErrorBoundary fallback={<RouteFallback route="Form Builder" />}><FormBuilder /></ErrorBoundary>} />
          <Route path="admin/contracts" element={<ErrorBoundary fallback={<RouteFallback route="Contracts" />}><ContractsManagement /></ErrorBoundary>} />
          <Route path="admin/settings" element={<ErrorBoundary fallback={<RouteFallback route="System Settings" />}><SystemSettings /></ErrorBoundary>} />
        </Route>
      </Routes>
      </Suspense>
      </PageErrorBoundary>
    </BrowserRouter>
    </ErrorBoundary>
    </QueryClientProvider>
  )
}

export default App
