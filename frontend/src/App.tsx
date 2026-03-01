import { useState, useEffect, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import Layout from './components/Layout'
import PortalLayout from './components/PortalLayout'
import { PortalAuthProvider } from './contexts/PortalAuthContext'

const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Incidents = lazy(() => import('./pages/Incidents'))
const IncidentDetail = lazy(() => import('./pages/IncidentDetail'))
const RTAs = lazy(() => import('./pages/RTAs'))
const RTADetail = lazy(() => import('./pages/RTADetail'))
const Complaints = lazy(() => import('./pages/Complaints'))
const ComplaintDetail = lazy(() => import('./pages/ComplaintDetail'))
const Policies = lazy(() => import('./pages/Policies'))
const Risks = lazy(() => import('./pages/Risks'))
const Audits = lazy(() => import('./pages/Audits'))
const Investigations = lazy(() => import('./pages/Investigations'))
const Standards = lazy(() => import('./pages/Standards'))
const Actions = lazy(() => import('./pages/Actions'))
const Documents = lazy(() => import('./pages/Documents'))
const AuditTemplateLibrary = lazy(() => import('./pages/AuditTemplateLibrary'))
const AuditTemplateBuilder = lazy(() => import('./pages/AuditTemplateBuilder'))
const AuditExecution = lazy(() => import('./pages/AuditExecution'))
const MobileAuditExecution = lazy(() => import('./pages/MobileAuditExecution'))
const Portal = lazy(() => import('./pages/Portal'))
const PortalLogin = lazy(() => import('./pages/PortalLogin'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))
const ResetPassword = lazy(() => import('./pages/ResetPassword'))
const PortalReport = lazy(() => import('./pages/PortalReport'))
const PortalTrack = lazy(() => import('./pages/PortalTrack'))
const PortalHelp = lazy(() => import('./pages/PortalHelp'))
const PortalIncidentForm = lazy(() => import('./pages/PortalIncidentForm'))
const PortalRTAForm = lazy(() => import('./pages/PortalRTAForm'))
const PortalNearMissForm = lazy(() => import('./pages/PortalNearMissForm'))
const PortalDynamicForm = lazy(() => import('./pages/PortalDynamicForm'))
const Analytics = lazy(() => import('./pages/Analytics'))
const GlobalSearch = lazy(() => import('./pages/GlobalSearch'))
const UserManagement = lazy(() => import('./pages/UserManagement'))
const AuditTrail = lazy(() => import('./pages/AuditTrail'))
const CalendarView = lazy(() => import('./pages/CalendarView'))
const Notifications = lazy(() => import('./pages/Notifications'))
const ExportCenter = lazy(() => import('./pages/ExportCenter'))
const ComplianceEvidence = lazy(() => import('./pages/ComplianceEvidence'))
const AdvancedAnalytics = lazy(() => import('./pages/AdvancedAnalytics'))
const DashboardBuilder = lazy(() => import('./pages/DashboardBuilder'))
const ReportGenerator = lazy(() => import('./pages/ReportGenerator'))
const WorkflowCenter = lazy(() => import('./pages/WorkflowCenter'))
const ComplianceAutomation = lazy(() => import('./pages/ComplianceAutomation'))
const RiskRegister = lazy(() => import('./pages/RiskRegister'))
const IMSDashboard = lazy(() => import('./pages/IMSDashboard'))
const AIIntelligence = lazy(() => import('./pages/AIIntelligence'))
const UVDBAudits = lazy(() => import('./pages/UVDBAudits'))
const PlanetMark = lazy(() => import('./pages/PlanetMark'))
const DigitalSignatures = lazy(() => import('./pages/DigitalSignatures'))
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'))
const FormsList = lazy(() => import('./pages/admin/FormsList'))
const FormBuilder = lazy(() => import('./pages/admin/FormBuilder'))
const ContractsManagement = lazy(() => import('./pages/admin/ContractsManagement'))
const SystemSettings = lazy(() => import('./pages/admin/SystemSettings'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="relative">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary/20 border-t-primary"></div>
      </div>
    </div>
  )
}

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
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
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
              <Route index element={<Portal />} />
              <Route path="report" element={<PortalReport />} />
              <Route path="report/incident" element={<PortalDynamicForm key="incident" formType="incident" />} />
              <Route path="report/near-miss" element={<PortalDynamicForm key="near-miss" formType="near-miss" />} />
              <Route path="report/complaint" element={<PortalDynamicForm key="complaint" formType="complaint" />} />
              <Route path="report/rta" element={<PortalRTAForm />} />
              <Route path="report/incident-legacy" element={<PortalIncidentForm />} />
              <Route path="report/near-miss-static" element={<PortalNearMissForm />} />
              <Route path="track" element={<PortalTrack />} />
              <Route path="track/:referenceNumber" element={<PortalTrack />} />
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
              <Route path="workflows" element={<WorkflowCenter />} />
              <Route path="compliance-automation" element={<ComplianceAutomation />} />
              <Route path="risk-register" element={<RiskRegister />} />
              <Route path="ims" element={<IMSDashboard />} />
              <Route path="ai-intelligence" element={<AIIntelligence />} />
              <Route path="uvdb" element={<UVDBAudits />} />
              <Route path="planet-mark" element={<PlanetMark />} />
              <Route path="signatures" element={<DigitalSignatures />} />
              <Route path="admin" element={<AdminDashboard />} />
              <Route path="admin/forms" element={<FormsList />} />
              <Route path="admin/forms/new" element={<FormBuilder />} />
              <Route path="admin/forms/:templateId" element={<FormBuilder />} />
              <Route path="admin/contracts" element={<ContractsManagement />} />
              <Route path="admin/settings" element={<SystemSettings />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
