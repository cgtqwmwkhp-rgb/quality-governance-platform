import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const mockGetDashboard = vi.fn()
const mockActionsSummary = vi.fn()
const mockViewCounts = vi.fn()
const mockRiskSummary = vi.fn()
const mockListRuns = vi.fn()
const mockComplianceScore = vi.fn()

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
  complianceAutomationApi: {
    getComplianceScore: (...args: unknown[]) => mockComplianceScore(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

describe('Analytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDashboard.mockResolvedValue({
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
        rtas: { total_in_period: 1 },
        risks: { total_active: 4, by_level: {}, high_critical: 1, average_score: 10 },
        kris: { total_active: 0, by_status: {}, at_risk: 0, pending_alerts: 0 },
        compliance: { total_assigned: 0, completed: 0, overdue: 0, completion_rate: 100 },
        sla_performance: { total_tracked: 0, met: 0, breached: 0, compliance_rate: 100 },
        trends: { incidents_weekly: [{ week_start: '2026-07-01', count: 2 }] },
        alerts: [],
      },
    })
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
          { id: 1, status: 'in_progress' },
          { id: 2, status: 'completed' },
        ],
      },
    })
    mockComplianceScore.mockResolvedValue({ data: { overall_score: 81.5 } })
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
})
