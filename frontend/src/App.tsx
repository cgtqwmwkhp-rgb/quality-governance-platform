import { useState, useEffect, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { startAutoSync } from './lib/syncService'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AnimatedOutlet } from './components/AnimatedOutlet'
import Layout from './components/Layout'
import PortalLayout from './components/PortalLayout'
import Login from './pages/Login'
import { PortalAuthProvider } from './contexts/PortalAuthContext'
import { useNotificationStore } from './stores'
import {
  getValidPlatformToken,
  establishPlatformSession,
  clearAuthState,
  revokeSession,
} from './utils/auth'
import { useFeatureFlag } from './hooks/useFeatureFlag'
import { LegacyActionItemRedirect } from './pages/actionLinks'
import { useSessionKeepalive } from './hooks/useSessionKeepalive'
import { useServiceWorkerAuthBridge } from './hooks/useServiceWorkerAuthBridge'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Incidents = lazy(() => import('./pages/Incidents'))
const IncidentDetail = lazy(() => import('./pages/IncidentDetail'))
const NearMisses = lazy(() => import('./pages/NearMisses'))
const NearMissDetail = lazy(() => import('./pages/NearMissDetail'))
const RTAs = lazy(() => import('./pages/RTAs'))
const RTADetail = lazy(() => import('./pages/RTADetail'))
const Complaints = lazy(() => import('./pages/Complaints'))
const ComplaintDetail = lazy(() => import('./pages/ComplaintDetail'))
const Policies = lazy(() => import('./pages/Policies'))
const Audits = lazy(() => import('./pages/Audits'))
const Investigations = lazy(() => import('./pages/Investigations'))
const InvestigationDetail = lazy(() => import('./pages/InvestigationDetail'))
const InvestigationTemplateBuilder = lazy(
  () => import('./pages/investigation-builder/InvestigationTemplateBuilder'),
)
const Standards = lazy(() => import('./pages/Standards'))
const Actions = lazy(() => import('./pages/Actions'))
const ActionDetail = lazy(() => import('./pages/ActionDetail'))
const Documents = lazy(() => import('./pages/Documents'))
const DocumentDetail = lazy(() => import('./pages/DocumentDetail'))
const DocumentControl = lazy(() => import('./pages/DocumentControl'))
const MyReading = lazy(() => import('./pages/MyReading'))
const KnowledgeExceptions = lazy(() => import('./pages/KnowledgeExceptions'))
const AuditTemplateLibrary = lazy(() => import('./pages/AuditTemplateLibrary'))
const AuditTemplateBuilder = lazy(() => import('./pages/AuditTemplateBuilder'))
const AuditExecution = lazy(() => import('./pages/AuditExecution'))
const AuditImportReview = lazy(() => import('./pages/AuditImportReview'))
const Portal = lazy(() => import('./pages/Portal'))
const PortalLogin = lazy(() => import('./pages/PortalLogin'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))
const ResetPassword = lazy(() => import('./pages/ResetPassword'))
const PortalReport = lazy(() => import('./pages/PortalReport'))
const PortalTrack = lazy(() => import('./pages/PortalTrack'))
const PortalHelp = lazy(() => import('./pages/PortalHelp'))
const PortalWork = lazy(() => import('./pages/PortalWork'))
const PortalIncidentForm = lazy(() => import('./pages/PortalIncidentForm'))
const PortalRTAForm = lazy(() => import('./pages/PortalRTAForm'))
const PortalNearMissForm = lazy(() => import('./pages/PortalNearMissForm'))
const PortalDynamicForm = lazy(() => import('./pages/PortalDynamicForm'))
const Analytics = lazy(() => import('./pages/Analytics'))
const GlobalSearch = lazy(() => import('./pages/GlobalSearch'))
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
const RiskProfile = lazy(() => import('./pages/RiskProfile'))
const IMSDashboard = lazy(() => import('./pages/IMSDashboard'))
const AIIntelligence = lazy(() => import('./pages/AIIntelligence'))
const UVDBAudits = lazy(() => import('./pages/UVDBAudits'))
const PlanetMark = lazy(() => import('./pages/PlanetMark'))
const CustomerAudits = lazy(() => import('./pages/CustomerAudits'))
const DigitalSignatures = lazy(() => import('./pages/DigitalSignatures'))
const VehicleChecklists = lazy(() => import('./pages/VehicleChecklists'))
const SafetyAssetRegister = lazy(() => import('./pages/SafetyAssetRegister'))
const SafetyAssetDetail = lazy(() => import('./pages/SafetyAssetDetail'))
const AssetHealthAnalytics = lazy(() => import('./pages/AssetHealthAnalytics'))
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
const CompetenceGaps = lazy(() => import('./pages/CompetenceGaps'))
const NotFound = lazy(() => import('./pages/NotFound'))
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'))
const FormsList = lazy(() => import('./pages/admin/FormsList'))
const FormBuilder = lazy(() => import('./pages/admin/FormBuilder'))
const ContractsManagement = lazy(() => import('./pages/admin/ContractsManagement'))
const SystemSettings = lazy(() => import('./pages/admin/SystemSettings'))
const AdminUserManagement = lazy(() => import('./pages/admin/UserManagement'))
const LookupTables = lazy(() => import('./pages/admin/LookupTables'))
const NotificationSettings = lazy(() => import('./pages/admin/NotificationSettings'))
const CampaignCompliance = lazy(() => import('./pages/admin/CampaignCompliance'))
const HsecQuestionInbox = lazy(() => import('./pages/admin/HsecQuestionInbox'))
const PartnerWebhooks = lazy(() => import('./pages/admin/PartnerWebhooks'))
const CampaignCompliance = lazy(() => import('./pages/admin/CampaignCompliance'))
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
          <svg
            className="w-6 h-6 text-destructive"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
        </div>
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            This section encountered an error
          </h3>
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

function RouteErrorBoundary() {
  const location = useLocation()
  return (
    <ErrorBoundary key={location.pathname} fallback={<RouteErrorFallback />}>
      <AnimatedOutlet />
    </ErrorBoundary>
  )
}

/** Legacy /risks routes redirect to Risk Register (orphan Risks.tsx retired). */
function RedirectToRiskRegister() {
  const { search } = useLocation()
  return <Navigate to={`/risk-register${search}`} replace />
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(getValidPlatformToken()))
  const adminUserManagementEnabled = useFeatureFlag('admin_user_management')

  // Keep the access JWT warm for long sessions (e.g. tablet auditors who
  // can sit on the questionnaire for >30 min between API calls without
  // realising the access token has expired).
  useSessionKeepalive({ enabled: isAuthenticated })

  // When the service worker reports a 401/403 from a fetch it intercepted,
  // trigger a silent token refresh instead of waiting for the next axios
  // call to discover the problem.
  useServiceWorkerAuthBridge({ enabled: isAuthenticated })

  useEffect(() => {
    if (isAuthenticated) {
      return startAutoSync(30000)
    }
  }, [isAuthenticated])

  const handleLogin = (token: string, refreshToken?: string) => {
    // Mirror JWT into portal storage so /portal/* works without a second Entra prompt.
    establishPlatformSession(token, refreshToken)
    setIsAuthenticated(true)
  }

  const handleLogout = async () => {
    await revokeSession()
    clearAuthState()
    useNotificationStore.getState().clearAll()
    setIsAuthenticated(false)
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
              <Route
                path="report/incident"
                element={<PortalDynamicForm key="incident" formType="incident" />}
              />
              <Route
                path="report/near-miss"
                element={<PortalDynamicForm key="near-miss" formType="near-miss" />}
              />
              <Route
                path="report/complaint"
                element={<PortalDynamicForm key="complaint" formType="complaint" />}
              />
              <Route path="report/rta" element={<PortalRTAForm />} />
              <Route path="report/incident-legacy" element={<PortalIncidentForm />} />
              <Route path="report/near-miss-static" element={<PortalNearMissForm />} />
              <Route path="track" element={<PortalTrack />} />
              <Route path="track/:referenceNumber" element={<PortalTrack />} />
              <Route path="work" element={<PortalWork />} />
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
                <Route path="near-misses" element={<NearMisses />} />
                <Route path="near-misses/:id" element={<NearMissDetail />} />
                <Route path="rtas" element={<RTAs />} />
                <Route path="rtas/:id" element={<RTADetail />} />
                <Route path="complaints" element={<Complaints />} />
                <Route path="complaints/:id" element={<ComplaintDetail />} />
                <Route path="vehicle-checklists" element={<VehicleChecklists />} />
                <Route path="safety-assets" element={<SafetyAssetRegister />} />
                <Route path="safety-assets/analytics" element={<AssetHealthAnalytics />} />
                <Route path="safety-assets/:id" element={<SafetyAssetDetail />} />
              </Route>

              {/* Governance routes */}
              <Route element={<RouteErrorBoundary />}>
                <Route path="audits" element={<Audits />} />
                <Route path="audit-templates" element={<AuditTemplateLibrary />} />
                <Route path="audit-templates/new" element={<AuditTemplateBuilder />} />
                <Route path="audit-templates/:templateId/edit" element={<AuditTemplateBuilder />} />
                <Route path="audits/:auditId/execute" element={<AuditExecution />} />
                <Route path="audits/:auditId/import-review" element={<AuditImportReview />} />
                <Route path="audits/:auditId/mobile" element={<AuditExecution />} />
                <Route path="investigations" element={<Investigations />} />
                <Route path="investigations/templates/builder" element={<InvestigationTemplateBuilder />} />
                <Route path="investigations/templates/builder/new" element={<InvestigationTemplateBuilder />} />
                <Route
                  path="investigations/templates/builder/:templateId/edit"
                  element={<InvestigationTemplateBuilder />}
                />
                <Route path="investigations/:id" element={<InvestigationDetail />} />
                <Route path="standards" element={<Standards />} />
                <Route path="actions" element={<Actions />} />
                <Route path="actions/item" element={<LegacyActionItemRedirect />} />
                <Route path="actions/:id" element={<ActionDetail />} />
                <Route path="compliance" element={<ComplianceEvidence />} />
                <Route path="uvdb" element={<UVDBAudits />} />
                <Route path="planet-mark" element={<PlanetMark />} />
                <Route path="customer-audits" element={<CustomerAudits />} />
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
                <Route path="documents/:id" element={<DocumentDetail />} />
                <Route path="document-control" element={<DocumentControl />} />
                <Route path="my-reading" element={<MyReading />} />
                <Route path="knowledge-exceptions" element={<KnowledgeExceptions />} />
                <Route path="policies" element={<Policies />} />
                <Route path="risks" element={<RedirectToRiskRegister />} />
                <Route path="risks/*" element={<RedirectToRiskRegister />} />
                {/* Golden-thread UAT: retire dead staff URLs with honest redirects */}
                <Route path="capa" element={<Navigate to="/actions?sourceType=capa" replace />} />
                <Route path="my-work" element={<Navigate to="/actions?view=mine" replace />} />
                <Route path="evidence" element={<Navigate to="/compliance" replace />} />
                <Route path="knowledge-bank" element={<Navigate to="/documents" replace />} />
                <Route path="exceptions" element={<Navigate to="/knowledge-exceptions" replace />} />
              </Route>

              {/* Workforce routes */}
              <Route element={<RouteErrorBoundary />}>
                <Route
                  path="workforce/assessments"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceAssessments />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/assessments/new"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceAssessmentCreate />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/assessments/:id/execute"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceAssessmentExecution />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/training"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceTraining />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/training/new"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceInductionCreate />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/training/:id/execute"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceTrainingExecution />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/engineers"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceEngineers />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/engineers/:id"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceEngineerProfile />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/calendar"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceCalendar />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/dashboard"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <WorkforceCompetencyDashboard />
                    </RequireRole>
                  }
                />
                <Route
                  path="workforce/competence-gaps"
                  element={
                    <RequireRole allowed={['admin', 'supervisor']}>
                      <CompetenceGaps />
                    </RequireRole>
                  }
                />
              </Route>

              {/* Admin & enterprise routes */}
              <Route element={<RouteErrorBoundary />}>
                <Route path="users" element={<Navigate to="/admin/users" replace />} />
                <Route path="audit-trail" element={<AuditTrail />} />
                <Route path="workflows" element={<WorkflowCenter />} />
                <Route path="compliance-automation" element={<ComplianceAutomation />} />
                <Route path="risk-register" element={<RiskRegister />} />
                <Route path="risk-register/:riskId" element={<RiskProfile />} />
                <Route path="ims" element={<IMSDashboard />} />
                <Route path="ai-intelligence" element={<AIIntelligence />} />
                <Route
                  path="admin"
                  element={
                    <RequireRole allowed={['admin', 'manager']}>
                      <AdminDashboard />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/forms"
                  element={
                    <RequireRole allowed={['admin', 'manager']}>
                      <FormsList />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/forms/new"
                  element={
                    <RequireRole allowed={['admin', 'manager']}>
                      <FormBuilder />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/forms/:templateId"
                  element={
                    <RequireRole allowed={['admin', 'manager']}>
                      <FormBuilder />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/contracts"
                  element={
                    <RequireRole allowed={['admin', 'manager']}>
                      <ContractsManagement />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/settings"
                  element={
                    <RequireRole allowed={['admin']}>
                      <SystemSettings />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/users"
                  element={
                    adminUserManagementEnabled ? (
                      <RequireRole allowed={['admin']} requireSuperuser>
                        <AdminUserManagement />
                      </RequireRole>
                    ) : (
                      <Navigate to="/admin" replace />
                    )
                  }
                />
                <Route
                  path="admin/lookups"
                  element={
                    <RequireRole allowed={['admin', 'manager']}>
                      <LookupTables />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/notifications"
                  element={
                    <RequireRole allowed={['admin']}>
                      <NotificationSettings />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/campaign-compliance"
                  element={
                    <RequireRole allowed={['admin', 'manager']}>
                      <CampaignCompliance />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/hsec-inbox"
                  element={
                    <RequireRole allowed={['admin', 'manager']}>
                      <HsecQuestionInbox />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/partner-webhooks"
                  element={
                    <RequireRole allowed={['admin']}>
                      <PartnerWebhooks />
                    </RequireRole>
                  }
                />
                <Route
                  path="admin/campaign-compliance"
                  element={
                    <RequireRole allowed={['admin', 'hsec']}>
                      <CampaignCompliance />
                    </RequireRole>
                  }
                />
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
