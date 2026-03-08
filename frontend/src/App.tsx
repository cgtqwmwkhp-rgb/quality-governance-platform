import { useState, useEffect, lazy, Suspense } from 'react'
import { useWebVitals } from './hooks/useWebVitals'
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { startAutoSync } from './lib/syncService'
import { ErrorBoundary } from './components/ErrorBoundary'
import Layout from './components/Layout'
import PortalLayout from './components/PortalLayout'
import { PortalAuthProvider } from './contexts/PortalAuthContext'
import { useNotificationStore } from './stores'
import { getPlatformToken, setAdminToken, clearTokens } from './utils/auth'

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
const InvestigationDetail = lazy(() => import('./pages/InvestigationDetail'))
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
const WorkforceAssessmentCreate = lazy(() => import('./pages/workforce/AssessmentCreate'))
const WorkforceInductionCreate = lazy(() => import('./pages/workforce/InductionCreate'))
const WorkforceAssessments = lazy(() => import('./pages/workforce/Assessments'))
const WorkforceAssessmentExecution = lazy(() => import('./pages/workforce/AssessmentExecution'))
const WorkforceTraining = lazy(() => import('./pages/workforce/Training'))
const WorkforceTrainingExecution = lazy(() => import('./pages/workforce/TrainingExecution'))
const WorkforceEngineers = lazy(() => import('./pages/workforce/Engineers'))
const WorkforceEngineerProfile = lazy(() => import('./pages/workforce/EngineerProfile'))
const WorkforceCalendar = lazy(() => import('./pages/workforce/Calendar'))
const WorkforceCompetencyDashboard = lazy(() => import('./pages/workforce/CompetencyDashboard'))
const NotFound = lazy(() => import('./pages/NotFound'))
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'))
const FormsList = lazy(() => import('./pages/admin/FormsList'))
const FormBuilder = lazy(() => import('./pages/admin/FormBuilder'))
const ContractsManagement = lazy(() => import('./pages/admin/ContractsManagement'))
const SystemSettings = lazy(() => import('./pages/admin/SystemSettings'))
const AdminUserManagement = lazy(() => import('./pages/admin/UserManagement'))
const LookupTables = lazy(() => import('./pages/admin/LookupTables'))
const NotificationSettings = lazy(() => import('./pages/admin/NotificationSettings'))
const RequireRole = lazy(() => import('./components/RequireRole'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="relative">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary/20 border-t-primary"></div>
      </div>
    </div>
  )
}

function RouteErrorFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="max-w-md w-full text-center space-y-4">
        <div className="mx-auto w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center">
          <svg className="w-6 h-6 text-destructive" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <div>
          <h3 className="text-lg font-semibold text-foreground">This section encountered an error</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            The rest of the application is still working. Try navigating to a different page.
          </p>
        </div>
        <div className="flex gap-3 justify-center">
          <a
            href="/dashboard"
            className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Go to Dashboard
          </a>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-foreground hover:bg-surface transition-colors"
          >
            Reload Page
          </button>
        </div>
      </div>
    </div>
  )
}

function AnimatedOutlet() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.15, ease: 'easeInOut' }}
      >
        <Outlet />
      </motion.div>
    </AnimatePresence>
  )
}

function RouteErrorBoundary() {
  const location = useLocation()
  return (
    <ErrorBoundary key={location.pathname} fallback={<RouteErrorFallback />}>
      <AnimatedOutlet />
    </ErrorBoundary>
  )
}

function App() {
  useWebVitals()
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = getPlatformToken()
    setIsAuthenticated(!!token)
    setIsLoading(false)
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      return startAutoSync(30000)
    }
  }, [isAuthenticated])

  const handleLogin = (token: string) => {
    setAdminToken(token)
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    clearTokens()
    useNotificationStore.getState().clearAll()
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

              {/* Core routes */}
              <Route element={<RouteErrorBoundary />}>
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="incidents" element={<Incidents />} />
                <Route path="incidents/:id" element={<IncidentDetail />} />
                <Route path="rtas" element={<RTAs />} />
                <Route path="rtas/:id" element={<RTADetail />} />
                <Route path="complaints" element={<Complaints />} />
                <Route path="complaints/:id" element={<ComplaintDetail />} />
              </Route>

              {/* Governance routes */}
              <Route element={<RouteErrorBoundary />}>
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
                <Route path="compliance" element={<ComplianceEvidence />} />
                <Route path="uvdb" element={<UVDBAudits />} />
                <Route path="planet-mark" element={<PlanetMark />} />
                <Route path="signatures" element={<DigitalSignatures />} />
              </Route>

              {/* Analytics & tools routes */}
              <Route element={<RouteErrorBoundary />}>
                <Route path="analytics" element={<Analytics />} />
                <Route path="analytics/advanced" element={<AdvancedAnalytics />} />
                <Route path="analytics/dashboards" element={<DashboardBuilder />} />
                <Route path="analytics/reports" element={<ReportGenerator />} />
                <Route path="search" element={<GlobalSearch />} />
                <Route path="calendar" element={<CalendarView />} />
                <Route path="notifications" element={<Notifications />} />
                <Route path="exports" element={<ExportCenter />} />
                <Route path="documents" element={<Documents />} />
                <Route path="policies" element={<Policies />} />
                <Route path="risks" element={<Risks />} />
              </Route>

              {/* Workforce routes */}
              <Route element={<RouteErrorBoundary />}>
                <Route path="workforce/assessments" element={<WorkforceAssessments />} />
                <Route path="workforce/assessments/new" element={<WorkforceAssessmentCreate />} />
                <Route path="workforce/assessments/:id/execute" element={<WorkforceAssessmentExecution />} />
                <Route path="workforce/training" element={<WorkforceTraining />} />
                <Route path="workforce/training/new" element={<WorkforceInductionCreate />} />
                <Route path="workforce/training/:id/execute" element={<WorkforceTrainingExecution />} />
                <Route path="workforce/engineers" element={<WorkforceEngineers />} />
                <Route path="workforce/engineers/:id" element={<WorkforceEngineerProfile />} />
                <Route path="workforce/calendar" element={<WorkforceCalendar />} />
                <Route path="workforce/dashboard" element={<WorkforceCompetencyDashboard />} />
              </Route>

              {/* Admin & enterprise routes */}
              <Route element={<RouteErrorBoundary />}>
                <Route path="users" element={<UserManagement />} />
                <Route path="audit-trail" element={<AuditTrail />} />
                <Route path="workflows" element={<WorkflowCenter />} />
                <Route path="compliance-automation" element={<ComplianceAutomation />} />
                <Route path="risk-register" element={<RiskRegister />} />
                <Route path="ims" element={<IMSDashboard />} />
                <Route path="ai-intelligence" element={<AIIntelligence />} />
                <Route path="admin" element={<RequireRole allowed={['admin', 'manager']}><AdminDashboard /></RequireRole>} />
                <Route path="admin/forms" element={<RequireRole allowed={['admin', 'manager']}><FormsList /></RequireRole>} />
                <Route path="admin/forms/new" element={<RequireRole allowed={['admin', 'manager']}><FormBuilder /></RequireRole>} />
                <Route path="admin/forms/:templateId" element={<RequireRole allowed={['admin', 'manager']}><FormBuilder /></RequireRole>} />
                <Route path="admin/contracts" element={<RequireRole allowed={['admin', 'manager']}><ContractsManagement /></RequireRole>} />
                <Route path="admin/settings" element={<RequireRole allowed={['admin']}><SystemSettings /></RequireRole>} />
                <Route path="admin/users" element={<RequireRole allowed={['admin']}><AdminUserManagement /></RequireRole>} />
                <Route path="admin/lookups" element={<RequireRole allowed={['admin', 'manager']}><LookupTables /></RequireRole>} />
                <Route path="admin/notifications" element={<RequireRole allowed={['admin']}><NotificationSettings /></RequireRole>} />
              </Route>

              {/* Catch-all 404 */}
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
