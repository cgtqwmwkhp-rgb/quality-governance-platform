import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'

const isAIIntelligenceRouteEnabledMock = vi.fn(() => false)

function createToken(expOffsetSeconds: number): string {
  const payload = btoa(JSON.stringify({ sub: '1', exp: Math.floor(Date.now() / 1000) + expOffsetSeconds }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '')
  return `header.${payload}.signature`
}

/**
 * RequireRole reads the role claim off the token, so a workforce route needs
 * one. Supervisor rather than admin on purpose: admin also opens the Layout's
 * pending-safety-lookups badge, which would drag an unrelated API call into a
 * routing assertion.
 */
function createSupervisorToken(expOffsetSeconds: number): string {
  const payload = btoa(
    JSON.stringify({
      sub: '1',
      role: 'supervisor',
      exp: Math.floor(Date.now() / 1000) + expOffsetSeconds,
    }),
  )
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '')
  return `header.${payload}.signature`
}

/** CB-UI-2's bind screen is admin-only, so its route assertion needs the claim. */
function createAdminToken(expOffsetSeconds: number): string {
  const payload = btoa(
    JSON.stringify({
      sub: '1',
      role: 'admin',
      exp: Math.floor(Date.now() / 1000) + expOffsetSeconds,
    }),
  )
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '')
  return `header.${payload}.signature`
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../lib/syncService', () => ({
  startAutoSync: vi.fn(() => vi.fn()),
}))

vi.mock('../services/errorTracker', () => ({
  trackComponentError: vi.fn(),
}))

// The authenticated tree reaches apiBase. Without this mock it throws into the
// ErrorBoundary and every assertion below would pass against an error screen
// rather than the real app.
vi.mock('../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
  detectEnvironment: () => 'production',
}))

vi.mock('../config/aiIntelligenceRoute', () => ({
  isAIIntelligenceRouteEnabled: () => isAIIntelligenceRouteEnabledMock(),
}))

vi.mock('../api/client', () => ({
  notificationsApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }),
  },
}))

// Layout only fetches the pending-safety-lookups badge on an admin/manager/hsec
// token, and the real client reaches for the axios instance this file mocks
// away. Without the stub an admin-gated route cannot be asserted through the
// real route table at all — the call throws into the route error boundary.
vi.mock('../api/safetyAssetsClient', () => ({
  safetyAssetsApi: {
    listPendingSafetyLookups: vi.fn().mockResolvedValue({ data: { total: 0, items: [] } }),
  },
}))

vi.mock('../components/copilot/AICopilot', () => ({
  default: () => <div data-testid="ai-copilot" />,
}))

vi.mock('../components/OfflineIndicator', () => ({
  default: () => null,
}))

vi.mock('../components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

vi.mock('../pages/Login', () => ({
  default: ({ onLogin: _onLogin }: { onLogin: (t: string) => void }) => (
    <div data-testid="login-page">
      <h1>Sign In</h1>
      <input data-testid="email-input" type="email" />
    </div>
  ),
}))

vi.mock('../pages/Dashboard', () => ({
  default: () => <div data-testid="dashboard-page">Dashboard</div>,
}))

vi.mock('../pages/ForgotPassword', () => ({
  default: () => <div>ForgotPassword</div>,
}))

vi.mock('../pages/ResetPassword', () => ({
  default: () => <div>ResetPassword</div>,
}))

vi.mock('../pages/Portal', () => ({ default: () => <div>Portal</div> }))
vi.mock('../pages/PortalLogin', () => ({ default: () => <div>PortalLogin</div> }))
vi.mock('../pages/PortalReport', () => ({ default: () => <div>PortalReport</div> }))
vi.mock('../pages/PortalTrack', () => ({ default: () => <div>PortalTrack</div> }))
vi.mock('../pages/PortalHelp', () => ({ default: () => <div>PortalHelp</div> }))
vi.mock('../pages/PortalIncidentForm', () => ({ default: () => <div>PortalIncidentForm</div> }))
vi.mock('../pages/PortalRTAForm', () => ({ default: () => <div>PortalRTAForm</div> }))
vi.mock('../pages/PortalNearMissForm', () => ({ default: () => <div>PortalNearMissForm</div> }))
vi.mock('../pages/PortalDynamicForm', () => ({ default: () => <div>PortalDynamicForm</div> }))
vi.mock('../pages/Incidents', () => ({ default: () => <div>Incidents</div> }))
vi.mock('../pages/IncidentDetail', () => ({ default: () => <div>IncidentDetail</div> }))
vi.mock('../pages/RTAs', () => ({ default: () => <div>RTAs</div> }))
vi.mock('../pages/RTADetail', () => ({ default: () => <div>RTADetail</div> }))
vi.mock('../pages/Complaints', () => ({ default: () => <div>Complaints</div> }))
vi.mock('../pages/ComplaintDetail', () => ({ default: () => <div>ComplaintDetail</div> }))
vi.mock('../pages/Policies', () => ({ default: () => <div>Policies</div> }))
vi.mock('../pages/Audits', () => ({ default: () => <div>Audits</div> }))
vi.mock('../pages/Investigations', () => ({ default: () => <div>Investigations</div> }))
vi.mock('../pages/Standards', () => ({ default: () => <div>Standards</div> }))
vi.mock('../pages/Actions', () => ({ default: () => <div>Actions</div> }))
vi.mock('../pages/Documents', () => ({ default: () => <div>Documents</div> }))
vi.mock('../pages/RegisterOfRegisters', () => ({ default: () => <div>RegisterOfRegisters</div> }))
vi.mock('../pages/AuditTemplateLibrary', () => ({ default: () => <div>AuditTemplateLibrary</div> }))
vi.mock('../pages/AuditTemplateBuilder', () => ({ default: () => <div>AuditTemplateBuilder</div> }))
vi.mock('../pages/AuditExecution', () => ({ default: () => <div>AuditExecution</div> }))
vi.mock('../pages/Analytics', () => ({ default: () => <div>Analytics</div> }))
vi.mock('../pages/GlobalSearch', () => ({ default: () => <div>GlobalSearch</div> }))
vi.mock('../pages/UserManagement', () => ({ default: () => <div>UserManagement</div> }))
vi.mock('../pages/AuditTrail', () => ({ default: () => <div>AuditTrail</div> }))
vi.mock('../pages/CalendarView', () => ({ default: () => <div>CalendarView</div> }))
vi.mock('../pages/Notifications', () => ({ default: () => <div>Notifications</div> }))
vi.mock('../pages/ExportCenter', () => ({ default: () => <div>ExportCenter</div> }))
vi.mock('../pages/ComplianceEvidence', () => ({ default: () => <div>ComplianceEvidence</div> }))
vi.mock('../pages/AdvancedAnalytics', () => ({ default: () => <div>AdvancedAnalytics</div> }))
vi.mock('../pages/DashboardBuilder', () => ({ default: () => <div>DashboardBuilder</div> }))
vi.mock('../pages/ReportGenerator', () => ({ default: () => <div>ReportGenerator</div> }))
vi.mock('../pages/ComplianceAutomation', () => ({ default: () => <div>ComplianceAutomation</div> }))
vi.mock('../pages/RiskRegister', () => ({ default: () => <div>RiskRegister</div> }))
vi.mock('../pages/IMSDashboard', () => ({ default: () => <div>IMSDashboard</div> }))
vi.mock('../pages/AIIntelligence', () => ({ default: () => <div>AIIntelligence</div> }))
vi.mock('../pages/UVDBAudits', () => ({ default: () => <div>UVDBAudits</div> }))
vi.mock('../pages/PlanetMark', () => ({ default: () => <div>PlanetMark</div> }))
vi.mock('../pages/DigitalSignatures', () => ({ default: () => <div>DigitalSignatures</div> }))
vi.mock('../pages/workforce/AssessmentCreate', () => ({
  default: () => <div>AssessmentCreate</div>,
}))
vi.mock('../pages/workforce/InductionCreate', () => ({ default: () => <div>InductionCreate</div> }))
vi.mock('../pages/workforce/Assessments', () => ({ default: () => <div>Assessments</div> }))
vi.mock('../pages/workforce/AssessmentExecution', () => ({
  default: () => <div>AssessmentExecution</div>,
}))
vi.mock('../pages/workforce/Training', () => ({ default: () => <div>Training</div> }))
vi.mock('../pages/workforce/TrainingExecution', () => ({
  default: () => <div>TrainingExecution</div>,
}))
vi.mock('../pages/workforce/Engineers', () => ({ default: () => <div>Engineers</div> }))
vi.mock('../pages/workforce/EngineerProfile', () => ({ default: () => <div>EngineerProfile</div> }))
vi.mock('../pages/workforce/CompetenceBoard', () => ({
  default: () => <div>CompetenceBoard</div>,
}))
vi.mock('../pages/workforce/CompetencyDashboard', () => ({
  default: () => <div>CompetencyDashboard</div>,
}))
vi.mock('../pages/admin/CompetenceBinds', () => ({
  default: () => <div>AdminCompetenceBinds</div>,
}))
vi.mock('../pages/admin/AdminDashboard', () => ({ default: () => <div>AdminDashboard</div> }))
vi.mock('../pages/admin/FormsList', () => ({ default: () => <div>FormsList</div> }))
vi.mock('../pages/admin/FormBuilder', () => ({ default: () => <div>FormBuilder</div> }))
vi.mock('../pages/admin/ContractsManagement', () => ({
  default: () => <div>ContractsManagement</div>,
}))
vi.mock('../pages/StaffHelp', () => ({ default: () => <div>StaffHelp</div> }))
vi.mock('../pages/admin/SystemSettings', () => ({ default: () => <div>SystemSettings</div> }))
vi.mock('../pages/admin/PartnerWebhooks', () => ({ default: () => <div>PartnerWebhooks</div> }))

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    delete window.__FEATURE_FLAGS__
    window.history.pushState({}, '', '/')
    isAIIntelligenceRouteEnabledMock.mockReset()
    isAIIntelligenceRouteEnabledMock.mockReturnValue(false)
  })

  // PX-179: an expired session dropped the user on /login with no route back
  // to the work they were in the middle of.
  it('remembers where an unauthenticated visitor was headed', async () => {
    window.history.pushState({}, '', '/help?topic=audits')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.getByTestId('login-page')).toBeInTheDocument()
    expect(sessionStorage.getItem('auth_return_path')).toBe('/help?topic=audits')
  })

  it('returns the user to where the session ended once they sign back in', async () => {
    sessionStorage.setItem('auth_return_path', '/help')
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/login')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(await screen.findByText('StaffHelp')).toBeInTheDocument()
    // Consumed, so a later sign-in starts from the dashboard again.
    expect(sessionStorage.getItem('auth_return_path')).toBeNull()
  })

  it('falls back to the dashboard when there is nothing to return to', async () => {
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/login')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(await screen.findByTestId('dashboard-page')).toBeInTheDocument()
  })

  it('ignores a return path that would redirect off-origin', async () => {
    sessionStorage.setItem('auth_return_path', '//evil.example/phish')
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/login')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(await screen.findByTestId('dashboard-page')).toBeInTheDocument()
  })

  it('renders login page when no token in localStorage', async () => {
    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.getByTestId('login-page')).toBeInTheDocument()
    expect(screen.getByTestId('email-input')).toBeInTheDocument()
  })

  it('does not show login page when token exists in localStorage', async () => {
    localStorage.setItem('access_token', createToken(3600))

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument()
  })

  it('renders login page when token is expired', async () => {
    localStorage.setItem('access_token', createToken(-3600))

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.getByTestId('login-page')).toBeInTheDocument()
  })

  // PX-285: typing the URL is the whole point — a missing sidebar link proves nothing.
  it('does not serve /ai-intelligence on direct navigation while the flag is off', async () => {
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/ai-intelligence')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.queryByText('AIIntelligence')).not.toBeInTheDocument()
    // The alias must not fall through to the Analyst it used to redirect to.
    expect(window.location.pathname).toBe('/ai-intelligence')
  })

  it('does not serve /ai-intelligence sub-paths while the flag is off', async () => {
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/ai-intelligence/insights')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.queryByText('AIIntelligence')).not.toBeInTheDocument()
    expect(window.location.pathname).toBe('/ai-intelligence/insights')
  })

  it('sends a bookmarked /workflows to the live action queue', async () => {
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/workflows')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(window.location.pathname).toBe('/actions')
    expect(window.location.search).toBe('?view=mine')
    expect(screen.getByText('Actions')).toBeInTheDocument()
  })

  // FR-WFFORCE-CAL-01: the workforce grid duplicated /calendar, which already
  // carries assessment and induction runs as training events.
  it('sends a bookmarked /workforce/calendar to the unified calendar feed', async () => {
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/workforce/calendar')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(window.location.pathname).toBe('/calendar')
    expect(window.location.search).toBe('?types=training')
    expect(screen.getByText('CalendarView')).toBeInTheDocument()
  })

  // FR-WF-CG-01: the competence gap board is folded into Actions on that source.
  it('sends a bookmarked /workforce/competence-gaps to the Actions register', async () => {
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/workforce/competence-gaps')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(window.location.pathname).toBe('/actions')
    expect(window.location.search).toBe('?sourceType=competence_gap')
    expect(screen.getByText('Actions')).toBeInTheDocument()
  })

  // CB-UI-1: Workforce → Competency is the competence board, not the WDP
  // workshop asset-type matrix it used to land on.
  it('serves the competence board at /workforce/dashboard', async () => {
    localStorage.setItem('access_token', createSupervisorToken(3600))
    window.history.pushState({}, '', '/workforce/dashboard')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.getByText('CompetenceBoard')).toBeInTheDocument()
    expect(screen.queryByText('CompetencyDashboard')).not.toBeInTheDocument()
  })

  // The WDP matrix stays reachable as the kill switch for that swap.
  it('keeps the WDP analytics matrix at /workforce/dashboard/analytics', async () => {
    localStorage.setItem('access_token', createSupervisorToken(3600))
    window.history.pushState({}, '', '/workforce/dashboard/analytics')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.getByText('CompetencyDashboard')).toBeInTheDocument()
    expect(screen.queryByText('CompetenceBoard')).not.toBeInTheDocument()
  })

  // CB-UI-2: the bind screen is an IT-Admin mapping job, so it is admin-gated
  // rather than sharing the supervisor board's role set.
  it('serves the competence bind screen at /admin/competence-binds for an admin', async () => {
    localStorage.setItem('access_token', createAdminToken(3600))
    window.history.pushState({}, '', '/admin/competence-binds')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.getByText('AdminCompetenceBinds')).toBeInTheDocument()
  })

  it('keeps the competence bind screen away from a supervisor', async () => {
    localStorage.setItem('access_token', createSupervisorToken(3600))
    window.history.pushState({}, '', '/admin/competence-binds')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.queryByText('AdminCompetenceBinds')).not.toBeInTheDocument()
  })

  // Wave 1 PR-A: Standards absorbed into /compliance programme shell.
  it('sends a bookmarked /standards URL to /compliance and preserves query params', async () => {
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/standards?code=ISO9001&clause=7.2')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(window.location.pathname).toBe('/compliance')
    expect(window.location.search).toBe('?code=ISO9001&clause=7.2&view=matrix')
    expect(screen.getByText('ComplianceEvidence')).toBeInTheDocument()
  })

  it('does not serve /registers on direct navigation while register_catalogue is off', async () => {
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/registers')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.queryByText('RegisterOfRegisters')).not.toBeInTheDocument()
    expect(window.location.pathname).toBe('/registers')
  })

  it('serves /registers on direct navigation when register_catalogue is on', async () => {
    window.__FEATURE_FLAGS__ = { register_catalogue: true }
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/registers')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(await screen.findByText('RegisterOfRegisters')).toBeInTheDocument()
    delete window.__FEATURE_FLAGS__
  })

  it('serves /ai-intelligence on direct navigation when the flag is on', async () => {
    isAIIntelligenceRouteEnabledMock.mockReturnValue(true)
    localStorage.setItem('access_token', createToken(3600))
    window.history.pushState({}, '', '/ai-intelligence')

    const App = (await import('../App')).default

    await act(async () => {
      render(<App />)
    })

    expect(screen.getByText('AIIntelligence')).toBeInTheDocument()
  })
})
