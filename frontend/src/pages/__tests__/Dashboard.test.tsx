import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}))

const emptyPage = { data: { items: [], total: 0 } }

const engineersApi = { getByUserMe: vi.fn() }
const portalComplianceApi = { myCompliance: vi.fn() }
const trainingMatrixApi = { myTraining: vi.fn(), getSummary: vi.fn() }
const actionsApi = { viewCounts: vi.fn() }
const incidentsApi = { list: vi.fn() }
const complaintsApi = { list: vi.fn() }
const nearMissesApi = { list: vi.fn() }
const rtasApi = { list: vi.fn() }
const executiveDashboardApi = { getDashboard: vi.fn() }
const auditsApi = { listRuns: vi.fn() }
const riskRegisterApi = { getSummary: vi.fn(), getTrends: vi.fn() }
const notificationsApi = { getUnreadCount: vi.fn() }
const assetHealthAnalyticsApi = { getSummary: vi.fn() }
const authMocks = { hasRole: vi.fn(), isSuperuser: vi.fn() }

vi.mock('../../api/client', () => ({
  engineersApi,
  portalComplianceApi,
  trainingMatrixApi,
  actionsApi,
  incidentsApi,
  complaintsApi,
  nearMissesApi,
  rtasApi,
  executiveDashboardApi,
  auditsApi,
  riskRegisterApi,
  notificationsApi,
}))

vi.mock('../../api/assetHealthAnalyticsClient', () => ({
  assetHealthAnalyticsApi,
}))

vi.mock('../../utils/auth', () => authMocks)

/** Default: unlinked, non-org user — every fetch resolves to an honest "empty". */
function applyDefaultMocks() {
  engineersApi.getByUserMe.mockResolvedValue({ data: { linked: false } })
  authMocks.hasRole.mockReturnValue(false)
  authMocks.isSuperuser.mockReturnValue(false)
  portalComplianceApi.myCompliance.mockResolvedValue({
    clear_state: 'clear',
    tool_summary: { total: 0, overdue: 0, due_30: 0, due_60: 0, due_90: 0, in_date: 0, quarantined: 0, mine: 0, on_van: 0 },
    tool_badge: 0,
    van_summary: { defect_counts: { p1: 0, p2: 0, p3: 0, total: 0 }, assignment_conflict: false },
    van_badge: 0,
  })
  trainingMatrixApi.myTraining.mockResolvedValue({ items: [], total: 0, atlas_hub_url: '' })
  trainingMatrixApi.getSummary.mockResolvedValue({
    module_ok: [{ role: 'Overall', ok: 0, total: 0, pct: 0, metric: 'module_ok' }],
    people_fully_ok: [],
    horizons: {},
    top_overdue_courses: [],
    required_row_count: 0,
    person_count: 0,
    atlas_hub_url: '',
  })
  actionsApi.viewCounts.mockResolvedValue({ data: { all: 0, my: 0, overdue: 0, my_overdue: 0 } })
  incidentsApi.list.mockResolvedValue(emptyPage)
  complaintsApi.list.mockResolvedValue(emptyPage)
  nearMissesApi.list.mockResolvedValue(emptyPage)
  rtasApi.list.mockResolvedValue(emptyPage)
  const weekSeries = Array.from({ length: 8 }, (_, i) => ({
    week_start: `2026-05-${String(i + 1).padStart(2, '0')}`,
    count: i,
    value: i * 10,
  }))
  executiveDashboardApi.getDashboard.mockImplementation(async (days: number) => ({
    data: {
      incidents: { total_in_period: days === 7 ? 2 : 10 },
      complaints: { total_in_period: days === 7 ? 1 : 4 },
      near_misses: { total_in_period: days === 7 ? 3 : 8 },
      trends: {
        incidents_weekly: weekSeries,
        complaints_weekly: weekSeries,
        near_misses_weekly: weekSeries,
        audits_weekly: weekSeries,
        training_compliance_weekly: weekSeries,
        tool_compliance_weekly: weekSeries,
      },
    },
  }))
  auditsApi.listRuns.mockResolvedValue(emptyPage)
  riskRegisterApi.getSummary.mockResolvedValue({ data: { total_risks: 0, by_category: {} } })
  riskRegisterApi.getTrends.mockResolvedValue({ data: { series: [] } })
  notificationsApi.getUnreadCount.mockResolvedValue({ data: { unread_count: 0 } })
  assetHealthAnalyticsApi.getSummary.mockResolvedValue({
    data: {
      total: 10,
      expiry_bands: { overdue: 0, due_30: 0, due_60: 0, due_90: 0, in_date: 10 },
      by_type: {},
      by_status: { quarantined: 0 },
      generated_at: '2026-07-21T00:00:00Z',
    },
  })
}

describe('Dashboard (role-aware living dashboard)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    applyDefaultMocks()
  })

  it('renders without crashing and shows the dashboard heading', async () => {
    const Dashboard = (await import('../Dashboard')).default
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>,
    )
    const heading = await screen.findByRole('heading', { name: 'Dashboard' })
    expect(heading).toBeInTheDocument()
  })

  it('shows the "all clear" honest empty rail when there are no priority items', async () => {
    const Dashboard = (await import('../Dashboard')).default
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>,
    )
    await screen.findByRole('heading', { name: 'Dashboard' })
    expect(await screen.findByTestId('highlight-rail-empty')).toBeInTheDocument()
  })

  describe('persona-aware layout (locked design §5)', () => {
    it('linked engineer (no org role) sees My Day only — no org/pulse strip', async () => {
      engineersApi.getByUserMe.mockResolvedValue({ data: { linked: true } })
      authMocks.hasRole.mockReturnValue(false)
      authMocks.isSuperuser.mockReturnValue(false)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      expect(await screen.findByTestId('my-day-section')).toBeInTheDocument()
      expect(screen.queryByTestId('pulse-trends-strip')).not.toBeInTheDocument()
      expect(screen.queryByTestId('org-command-strip')).not.toBeInTheDocument()
    })

    it('admin/manager without an engineer link sees Org first — no My Day', async () => {
      engineersApi.getByUserMe.mockResolvedValue({ data: { linked: false } })
      authMocks.hasRole.mockReturnValue(true) // admin/manager
      authMocks.isSuperuser.mockReturnValue(false)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      expect(await screen.findByTestId('pulse-trends-strip')).toBeInTheDocument()
      expect(await screen.findByTestId('org-command-strip')).toBeInTheDocument()
      expect(screen.queryByTestId('my-day-section')).not.toBeInTheDocument()
    })

    it('dual-role (linked engineer AND admin/manager) sees My Day first plus a compact org strip', async () => {
      engineersApi.getByUserMe.mockResolvedValue({ data: { linked: true } })
      authMocks.hasRole.mockReturnValue(true)
      authMocks.isSuperuser.mockReturnValue(false)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const myDay = await screen.findByTestId('my-day-section')
      const orgStrip = await screen.findByTestId('org-command-strip')
      expect(myDay).toBeInTheDocument()
      expect(orgStrip).toBeInTheDocument()
      // My Day is stage-first for dual-role users (locked design §2/§5).
      expect(myDay.compareDocumentPosition(orgStrip) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })
  })

  describe('fail-honest rendering', () => {
    it('shows an unavailable dash instead of a fabricated zero when a pulse fetch fails', async () => {
      authMocks.hasRole.mockReturnValue(true)
      assetHealthAnalyticsApi.getSummary.mockRejectedValue(new Error('network down'))

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const toolComplianceValue = await screen.findByTestId('pulse-tool-compliance-value')
      expect(toolComplianceValue).toHaveTextContent('—')
      expect(toolComplianceValue).not.toHaveTextContent('0')
    })

    // Superseded 28/07/2026: this previously asserted 100% for an empty registry.
    // David's decision is that zero registered assets is an unpopulated registry
    // rather than a compliant fleet, so it must read unavailable — matching the
    // training tile, which had the same empty denominator rendered as 0%.
    it('empty asset registry shows an unavailable dash, not 100% tool compliance', async () => {
      authMocks.hasRole.mockReturnValue(true)
      assetHealthAnalyticsApi.getSummary.mockResolvedValue({
        data: {
          total: 0,
          expiry_bands: { overdue: 0, due_30: 0, due_60: 0, due_90: 0, in_date: 0 },
          by_type: {},
          by_status: { quarantined: 0 },
          generated_at: '2026-07-21T00:00:00Z',
        },
      })

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const toolComplianceValue = await screen.findByTestId('pulse-tool-compliance-value')
      expect(toolComplianceValue).toHaveTextContent('—')
      expect(toolComplianceValue).not.toHaveTextContent('100')
    })

    it('shows a real tool-compliance percentage once the registry has assets', async () => {
      authMocks.hasRole.mockReturnValue(true)
      assetHealthAnalyticsApi.getSummary.mockResolvedValue({
        data: {
          total: 20,
          expiry_bands: { overdue: 3, due_30: 0, due_60: 0, due_90: 0, in_date: 17 },
          by_type: {},
          by_status: { quarantined: 1 },
          generated_at: '2026-07-21T00:00:00Z',
        },
      })

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const toolComplianceValue = await screen.findByTestId('pulse-tool-compliance-value')
      expect(toolComplianceValue).toHaveTextContent('80%')
    })

    it('no training requirements defined shows an unavailable dash, not 0% compliance', async () => {
      authMocks.hasRole.mockReturnValue(true)
      // Default mock is already staging's shape: Overall 0/0, required_row_count 0.
      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const trainingValue = await screen.findByTestId('pulse-training-compliance-value')
      expect(trainingValue).toHaveTextContent('—')
      expect(trainingValue).not.toHaveTextContent('0')
    })

    it('shows the real training percentage once a denominator exists', async () => {
      authMocks.hasRole.mockReturnValue(true)
      trainingMatrixApi.getSummary.mockResolvedValue({
        module_ok: [{ role: 'Overall', ok: 41, total: 50, pct: 82, metric: 'module_ok' }],
        people_fully_ok: [],
        horizons: {},
        top_overdue_courses: [],
        required_row_count: 50,
        person_count: 12,
        atlas_hub_url: '',
      })

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const trainingValue = await screen.findByTestId('pulse-training-compliance-value')
      expect(trainingValue).toHaveTextContent('82%')
    })

    it('keeps My Day when engineer link probe fails (does not treat as unlinked)', async () => {
      engineersApi.getByUserMe.mockRejectedValue(new Error('timeout'))
      authMocks.hasRole.mockReturnValue(false)
      authMocks.isSuperuser.mockReturnValue(false)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      expect(await screen.findByTestId('my-day-section')).toBeInTheDocument()
      expect(screen.queryByTestId('org-command-strip')).not.toBeInTheDocument()
      expect(await screen.findByText(/Could not verify your engineer profile link/i)).toBeInTheDocument()
    })

    it('shows an unavailable dash on the org asset-health tile when the fetch fails', async () => {
      authMocks.hasRole.mockReturnValue(true)
      assetHealthAnalyticsApi.getSummary.mockRejectedValue(new Error('network down'))

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const assetTile = await screen.findByTestId('org-asset-health-tile')
      expect(assetTile).toHaveTextContent('—')
      expect(assetTile).toHaveTextContent('Metrics are currently unavailable.')
    })
  })

  describe('pulse drill-down links', () => {
    it('the Training compliance pulse tile deep-links to the workforce dashboard', async () => {
      authMocks.hasRole.mockReturnValue(true)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const tile = await screen.findByTestId('pulse-training-compliance')
      expect(tile.tagName).toBe('A')
      expect(tile).toHaveAttribute('href', '/workforce/dashboard')
    })

    it('the Incidents (7d) pulse tile deep-links to the incidents list', async () => {
      authMocks.hasRole.mockReturnValue(true)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const tile = await screen.findByTestId('pulse-incidents-7d')
      expect(tile).toHaveAttribute('href', '/incidents')
    })

    it('renders a sparkline on pulse tiles when weekly series is present', async () => {
      authMocks.hasRole.mockReturnValue(true)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      expect(await screen.findByTestId('pulse-incidents-7d-sparkline')).toBeInTheDocument()
      // Training sparkline intentionally omitted (module_ok ≠ expiry backcast).
      expect(screen.queryByTestId('pulse-training-compliance-sparkline')).not.toBeInTheDocument()
      expect(screen.getByTestId('pulse-tool-compliance-sparkline')).toBeInTheDocument()
    })
  })

  describe('recent cases cascade', () => {
    it('shows tab switcher for incidents / near misses / complaints / RTAs', async () => {
      authMocks.hasRole.mockReturnValue(true)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      expect(await screen.findByTestId('recent-cases-panel')).toBeInTheDocument()
      expect(screen.getByTestId('recent-cases-tab-incidents')).toBeInTheDocument()
      expect(screen.getByTestId('recent-cases-tab-near_misses')).toBeInTheDocument()
      expect(screen.getByTestId('recent-cases-tab-complaints')).toBeInTheDocument()
      expect(screen.getByTestId('recent-cases-tab-rtas')).toBeInTheDocument()
    })
  })

  // compliance_schedule on the executive-dashboard payload is null when the
  // deployment opener is off, the kill switch is engaged, or the caller lacks
  // compliance_schedule:read. The tile must be absent rather than empty.
  describe('Compliance Schedule tile (flag + permission gated)', () => {
    function withComplianceSchedule(
      cs:
        | {
            available: boolean
            total_active: number | null
            current: number | null
            due_soon: number | null
            overdue: number | null
            href?: string
          }
        | null
        | undefined,
    ) {
      const weekSeries = Array.from({ length: 8 }, (_, i) => ({
        week_start: `2026-05-${String(i + 1).padStart(2, '0')}`,
        count: i,
        value: i * 10,
      }))
      executiveDashboardApi.getDashboard.mockImplementation(async (days: number) => ({
        data: {
          incidents: { total_in_period: days === 7 ? 2 : 10 },
          complaints: { total_in_period: days === 7 ? 1 : 4 },
          near_misses: { total_in_period: days === 7 ? 3 : 8 },
          trends: {
            incidents_weekly: weekSeries,
            complaints_weekly: weekSeries,
            near_misses_weekly: weekSeries,
            audits_weekly: weekSeries,
            training_compliance_weekly: weekSeries,
            tool_compliance_weekly: weekSeries,
          },
          compliance_schedule: cs,
        },
      }))
    }

    it('omits the tile entirely when the module is closed to the caller', async () => {
      authMocks.hasRole.mockReturnValue(true)
      withComplianceSchedule(null)

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })
      await screen.findByTestId('org-command-strip')

      expect(screen.queryByTestId('org-compliance-schedule-tile')).not.toBeInTheDocument()
    })

    it("shows the register's own counts when the module is open", async () => {
      authMocks.hasRole.mockReturnValue(true)
      withComplianceSchedule({
        available: true,
        total_active: 12,
        current: 7,
        due_soon: 3,
        overdue: 2,
        href: '/compliance-schedule',
      })

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const tile = await screen.findByTestId('org-compliance-schedule-tile')
      expect(tile).toHaveAttribute('href', '/compliance-schedule')
      expect(screen.getByTestId('org-compliance-schedule-value')).toHaveTextContent('12')
      expect(tile).toHaveTextContent('2 overdue')
      expect(tile).toHaveTextContent('3 due soon')
      expect(tile).toHaveTextContent('7 current')
    })

    it('shows an unavailable dash, not a fabricated zero, when stats are unread', async () => {
      authMocks.hasRole.mockReturnValue(true)
      withComplianceSchedule({
        available: false,
        total_active: null,
        current: null,
        due_soon: null,
        overdue: null,
        href: '/compliance-schedule',
      })

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByRole('heading', { name: 'Dashboard' })

      const tile = await screen.findByTestId('org-compliance-schedule-tile')
      const value = screen.getByTestId('org-compliance-schedule-value')
      expect(value).toHaveTextContent('—')
      expect(value).not.toHaveTextContent('0')
      expect(tile).toHaveTextContent('Metrics are currently unavailable.')
      expect(tile).not.toHaveTextContent('overdue')
    })

    it('does not show the tile for a persona that has no org strip', async () => {
      engineersApi.getByUserMe.mockResolvedValue({ data: { linked: true } })
      authMocks.hasRole.mockReturnValue(false)
      authMocks.isSuperuser.mockReturnValue(false)
      withComplianceSchedule({
        available: true,
        total_active: 12,
        current: 7,
        due_soon: 3,
        overdue: 2,
      })

      const Dashboard = (await import('../Dashboard')).default
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>,
      )
      await screen.findByTestId('my-day-section')

      expect(screen.queryByTestId('org-command-strip')).not.toBeInTheDocument()
      expect(screen.queryByTestId('org-compliance-schedule-tile')).not.toBeInTheDocument()
    })
  })
})
