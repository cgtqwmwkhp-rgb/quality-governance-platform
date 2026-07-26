import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const mockGetDashboard = vi.fn()
const mockActionsSummary = vi.fn()
const mockViewCounts = vi.fn()
const mockRiskSummary = vi.fn()
const mockListRuns = vi.fn()
const mockListRtas = vi.fn()
const mockComplianceScore = vi.fn()
const mockGetComplianceOverview = vi.fn()

vi.mock('../../api/client', () => ({
  executiveDashboardApi: {
    getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
  },
  actionsApi: {
    summary: (...args: unknown[]) => mockActionsSummary(...args),
    viewCounts: (...args: unknown[]) => mockViewCounts(...args),
  },
  riskRegisterApi: {
    getSummary: (...args: unknown[]) => mockRiskSummary(...args),
  },
  auditsApi: {
    listRuns: (...args: unknown[]) => mockListRuns(...args),
  },
  rtasApi: {
    list: (...args: unknown[]) => mockListRtas(...args),
  },
  complianceAutomationApi: {
    getComplianceScore: (...args: unknown[]) => mockComplianceScore(...args),
  },
  documentCampaignApi: {
    getComplianceOverview: (...args: unknown[]) => mockGetComplianceOverview(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

/** Base executive-dashboard payload. `rtas` is overridden per test for PX-223 cases. */
function dashboardFixture(rtas: Record<string, number> = { total_in_period: 2, total: 3, open: 1, closed: 2 }) {
  return {
    data: {
      generated_at: '2026-07-16T00:00:00Z',
      period_days: 30,
      health_score: { score: 72, status: 'ok', color: 'green', components: {} },
      incidents: {
        total_in_period: 5,
        open: 2,
        by_severity: {},
        sif_count: 0,
        psif_count: 0,
        critical_high: 1,
      },
      near_misses: {
        total_in_period: 1,
        previous_period: 0,
        trend_percent: 0,
        reporting_rate: 'stable',
      },
      complaints: {
        total_in_period: 3,
        open: 1,
        closed_in_period: 2,
        resolution_rate: 66.7,
      },
      rtas,
      risks: { total_active: 4, by_level: {}, high_critical: 1, average_score: 10 },
      audits: {
        totals: 2,
        completed: 1,
        in_progress: 1,
        avg_score: 85,
        pass_rate: 100,
        essential_compliance_pct: 100,
        incomplete_critical_count: 0,
      },
      kris: { total_active: 0, by_status: {}, at_risk: 0, pending_alerts: 0 },
      compliance: { total_assigned: 0, completed: 0, overdue: 0, completion_rate: 100 },
      sla_performance: { total_tracked: 0, met: 0, breached: 0, compliance_rate: 100 },
      trends: { incidents_weekly: [{ week_start: '2026-07-01', count: 2 }] },
      alerts: [],
    },
  }
}

describe('Analytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Register-wide total/open/closed alongside the windowed figure. The register holds
    // more than the 30-day window saw — the shape that used to render as Open > Total.
    mockGetDashboard.mockResolvedValue(dashboardFixture())
    mockActionsSummary.mockResolvedValue({
      data: { total: 10, by_display_status: { open: 4, completed: 6 } },
    })
    mockViewCounts.mockResolvedValue({
      data: { all: 10, my: 2, overdue: 3, my_overdue: 1 },
    })
    mockRiskSummary.mockResolvedValue({ data: { total_risks: 4 } })
    mockListRuns.mockResolvedValue({
      data: {
        total: 2,
        items: [
          {
            id: 1,
            status: 'in_progress',
            created_at: '2026-07-01T00:00:00Z',
          },
          {
            id: 2,
            status: 'completed',
            created_at: '2026-07-01T00:00:00Z',
            completed_at: '2026-07-06T00:00:00Z',
          },
        ],
      },
    })
    mockListRtas.mockResolvedValue({
      data: {
        total: 2,
        items: [
          {
            id: 1,
            status: 'open',
            created_at: '2026-07-01T00:00:00Z',
            reported_date: '2026-07-01T00:00:00Z',
          },
          {
            id: 2,
            status: 'closed',
            created_at: '2026-07-01T00:00:00Z',
            reported_date: '2026-07-01T00:00:00Z',
            updated_at: '2026-07-04T00:00:00Z',
          },
        ],
      },
    })
    mockComplianceScore.mockResolvedValue({ data: { overall_score: 81.5 } })
    mockGetComplianceOverview.mockResolvedValue({
      data: {
        active_campaigns: 2,
        total_assignments: 12,
        completed_assignments: 2,
        overall_completion_rate: 17,
        overdue_count: 0,
        quiz_fail_count: 1,
        unanswered_hseq_count: 0,
        open_rate: 17,
        series: [{ date: '2026-07-19', completed: 1, opened: 1, overdue: 0 }],
      },
    })
  })

  it('loads live KPIs and drills into a section', async () => {
    const Analytics = (await import('../Analytics')).default
    render(
      <MemoryRouter initialEntries={['/analytics']}>
        <Routes>
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('analytics-page')).toBeInTheDocument()
    expect(await screen.findByTestId('analytics-module-table')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Home' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('analytics-hero-open')).toHaveTextContent('Open items')
    expect(mockGetDashboard).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('tab', { name: 'Incidents' }))
    await waitFor(() => {
      expect(screen.getByTestId('analytics-section-panel')).toBeInTheDocument()
    })
    expect(screen.getByRole('link', { name: /Go to Incidents/i })).toHaveAttribute(
      'href',
      '/incidents',
    )
  })

  it('renders Document campaigns section with campaign command KPIs', async () => {
    const Analytics = (await import('../Analytics')).default
    render(
      <MemoryRouter initialEntries={['/analytics?section=document-campaigns']}>
        <Routes>
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('analytics-document-campaigns')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Document campaigns' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(await screen.findByTestId('campaign-command-kpis')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open Document campaigns/i })).toHaveAttribute(
      'href',
      '/documents/campaigns',
    )
    expect(mockGetComplianceOverview).toHaveBeenCalled()
  })

  describe('module metric honesty', () => {
    // Replaces 'shows RTA open/closed from list API instead of fake zeros'. That test
    // pinned the design behind PX-223: open/closed counted from one page of the register
    // while total came from the dashboard, so the two could never be made to reconcile.
    it('takes RTA total/open/closed from the dashboard aggregate so they reconcile', async () => {
      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={['/analytics?section=rtas']}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )

      const summary = await screen.findByTestId('analytics-rta-summary')
      expect(summary).toHaveTextContent(/Total[\s\S]*3/)
      expect(summary).toHaveTextContent(/Open[\s\S]*1/)
      expect(summary).toHaveTextContent(/Closed[\s\S]*2/)
      // Avg resolution stays page-scoped; the register page is fetched for that alone.
      expect(summary).toHaveTextContent('3.0d')
      expect(mockListRtas).toHaveBeenCalledWith(1, 100)

      const table = await screen.findByTestId('analytics-module-table')
      const rtaRow = within(table).getByRole('row', { name: /RTAs/i })
      expect(within(rtaRow).getByText('3')).toBeInTheDocument()
    })

    it('never lets RTA open exceed total, even when the window under-counts', async () => {
      // The reported numbers: a 30-day window holding 31 while the register holds 32.
      mockGetDashboard.mockResolvedValue(
        dashboardFixture({ total_in_period: 31, total: 32, open: 32, closed: 0 }),
      )
      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={['/analytics?section=rtas']}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )

      const summary = await screen.findByTestId('analytics-rta-summary')
      expect(summary).toHaveTextContent(/Total[\s\S]*32/)
      expect(summary).toHaveTextContent(/Open[\s\S]*32/)
      expect(summary).not.toHaveTextContent('31')
    })

    it('withholds RTA open/closed when the server omits the split', async () => {
      // A backend that predates the aggregate: the summary is present but has no split.
      mockGetDashboard.mockResolvedValue(dashboardFixture({ total_in_period: 2 }))
      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={['/analytics?section=rtas']}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )

      const summary = await screen.findByTestId('analytics-rta-summary')
      expect(summary).toHaveTextContent(/RTA open\/closed unavailable/i)
      expect(summary).not.toHaveTextContent('0')
    })

    it('shows dedicated audit summary with avg resolution when completion timestamps exist', async () => {
      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={['/analytics?section=audits']}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )

      const summary = await screen.findByTestId('analytics-audit-summary')
      expect(summary).toHaveTextContent('Audit summary')
      expect(summary).toHaveTextContent('5.0d')
      expect(summary).toHaveTextContent(/Open[\s\S]*1/)
      expect(summary).toHaveTextContent(/Closed[\s\S]*1/)
      expect(summary).toHaveTextContent(/Total[\s\S]*2/)
    })

    it('marks audit metrics unavailable without inventing zero counts', async () => {
      mockGetDashboard.mockRejectedValue(new Error('dashboard down'))
      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={['/analytics?section=audits']}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )

      const summary = await screen.findByTestId('analytics-audit-summary')
      expect(summary).toHaveTextContent(/Audit metrics unavailable/i)
      expect(summary).not.toHaveTextContent('0')
      expect(await screen.findByTestId('analytics-partial')).toHaveTextContent(
        /Executive dashboard unavailable/i,
      )

      const table = screen.getByTestId('analytics-module-table')
      const auditsRow = within(table).getByRole('row', { name: /Audits/i })
      expect(within(auditsRow).getAllByText('—').length).toBeGreaterThanOrEqual(3)
    })

    it('module distribution uses period-scoped totals and excludes register-only modules (PX-195)', async () => {
      mockGetDashboard.mockResolvedValue(
        dashboardFixture({
          total_in_period: 2,
          total: 50,
          open: 10,
          closed: 40,
        }),
      )
      mockRiskSummary.mockResolvedValue({ data: { total_risks: 129 } })
      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={['/analytics']}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )

      const distribution = await screen.findByTestId('analytics-module-distribution')
      expect(screen.getByText(/period-scoped/i)).toBeInTheDocument()
      expect(within(distribution).getByText('Incidents')).toBeInTheDocument()
      expect(within(distribution).getByText('Audits')).toBeInTheDocument()
      expect(within(distribution).queryByText('Risks')).not.toBeInTheDocument()
      expect(within(distribution).queryByText('Actions')).not.toBeInTheDocument()
      expect(screen.getByTestId('analytics-hero-compliance')).toHaveTextContent('Evidence coverage')
    })

    // Was 'marks RTA open/closed unavailable without inventing zero counts', driven by a
    // failing rtasApi.list. Open/closed no longer come from that call, so the dashboard is
    // now the dependency whose failure must withhold them.
    it('marks RTA open/closed unavailable when the aggregate cannot be loaded', async () => {
      mockGetDashboard.mockRejectedValue(new Error('dashboard down'))
      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={['/analytics?section=rtas']}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )

      const summary = await screen.findByTestId('analytics-rta-summary')
      expect(summary).toHaveTextContent(/RTA open\/closed unavailable/i)
      expect(summary).not.toHaveTextContent('0')

      const table = screen.getByTestId('analytics-module-table')
      const rtaRow = within(table).getByRole('row', { name: /RTAs/i })
      expect(within(rtaRow).getAllByText('—').length).toBeGreaterThanOrEqual(2)
    })

    it('still shows average resolution when only the register page fails', async () => {
      mockListRtas.mockRejectedValue(new Error('rtas down'))
      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={['/analytics?section=rtas']}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )

      const summary = await screen.findByTestId('analytics-rta-summary')
      expect(summary).toHaveTextContent(/Open[\s\S]*1/)
      expect(summary).toHaveTextContent(/Closed[\s\S]*2/)
      expect(await screen.findByTestId('analytics-partial')).toHaveTextContent(
        /average resolution not shown/i,
      )
    })
  })

  describe('trend honesty (PX-224)', () => {
    /**
     * The Incidents row used to render `near_misses.trend_percent`. With six near
     * misses against a baseline of one that printed "500.0%" next to an incident
     * chart that had no points at all.
     */
    async function renderWithNearMissSpike(route = '/analytics?section=incidents') {
      mockGetDashboard.mockResolvedValue({
        data: {
          generated_at: '2026-07-16T00:00:00Z',
          period_days: 30,
          health_score: { score: 72, status: 'ok', color: 'green', components: {} },
          incidents: {
            total_in_period: 0,
            open: 0,
            by_severity: {},
            sif_count: 0,
            psif_count: 0,
            critical_high: 0,
          },
          near_misses: {
            total_in_period: 6,
            previous_period: 1,
            trend_percent: 500.0,
            reporting_rate: 'improving',
          },
          complaints: {
            total_in_period: 0,
            open: 0,
            closed_in_period: 0,
            resolution_rate: null,
          },
          rtas: { total_in_period: 0 },
          risks: { total_active: 0, by_level: {}, high_critical: 0, average_score: 0 },
          kris: { total_active: 0, by_status: {}, at_risk: 0, pending_alerts: 0 },
          compliance: { total_assigned: 0, completed: 0, overdue: 0, completion_rate: 100 },
          sla_performance: { total_tracked: 0, met: 0, breached: 0, compliance_rate: 100 },
          trends: { incidents_weekly: [] },
          alerts: [],
        },
      })

      const Analytics = (await import('../Analytics')).default
      render(
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </MemoryRouter>,
      )
      return screen.findByTestId('analytics-module-table')
    }

    it('never shows the near-miss trend on the Incidents row', async () => {
      const table = await renderWithNearMissSpike()
      const incidentsRow = within(table).getByRole('row', { name: /Incidents/i })

      expect(incidentsRow).not.toHaveTextContent('500.0%')
      expect(incidentsRow).not.toHaveTextContent('500')
      expect(incidentsRow).toHaveTextContent('No data')
    })

    it('does not claim stability for modules the API reports no trend for', async () => {
      // Unfiltered so every module row is on screen.
      const table = await renderWithNearMissSpike('/analytics')

      // "No change" asserts the rate held steady. The exec-dashboard payload carries
      // no trend for any of these modules, so it has no basis to say so.
      for (const module of [/Incidents/i, /RTAs/i, /Complaints/i, /Audits/i]) {
        const row = within(table).getByRole('row', { name: module })
        expect(row).not.toHaveTextContent('No change')
        expect(row).toHaveTextContent('No data')
      }
    })

    it('shows no trend percentage anywhere while the incident chart is empty', async () => {
      await renderWithNearMissSpike()

      expect(await screen.findByTestId('analytics-trends')).toHaveTextContent(
        /No incident trend points for this period/i,
      )
      const table = screen.getByTestId('analytics-module-table')
      expect(within(table).queryByText(/\d+\.\d%/)).toBeNull()
    })
  })
})
