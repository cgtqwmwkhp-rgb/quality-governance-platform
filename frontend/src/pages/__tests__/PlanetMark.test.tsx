import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const mockGetDashboard = vi.fn()
const mockListYears = vi.fn()
const mockListSources = vi.fn()
const mockListActions = vi.fn()
const mockGetScope3 = vi.fn()
const mockGetCertification = vi.fn()
const mockGetDataQuality = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  planetMarkApi: {
    getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
    listYears: (...args: unknown[]) => mockListYears(...args),
    listSources: (...args: unknown[]) => mockListSources(...args),
    listActions: (...args: unknown[]) => mockListActions(...args),
    getScope3: (...args: unknown[]) => mockGetScope3(...args),
    getCertification: (...args: unknown[]) => mockGetCertification(...args),
    getDataQuality: (...args: unknown[]) => mockGetDataQuality(...args),
  },
  ErrorClass: {
    NETWORK_ERROR: 'NETWORK_ERROR',
    SERVER_ERROR: 'SERVER_ERROR',
    AUTH_ERROR: 'AUTH_ERROR',
    NOT_FOUND: 'NOT_FOUND',
    UNKNOWN: 'UNKNOWN',
  },
  createApiError: () => ({ error_class: 'UNKNOWN' }),
  isSetupRequired: (payload: Record<string, unknown>) => payload?.error_class === 'SETUP_REQUIRED',
}))

vi.mock('../../components/ui/SetupRequiredPanel', () => ({
  SetupRequiredPanel: () => <div>setup required</div>,
}))

describe('PlanetMark', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDashboard.mockResolvedValue({
      data: {
        current_year: {
          id: 1,
          label: 'YE2026',
          total_emissions: 22.1,
          emissions_per_fte: 1.1,
          fte: 20,
          yoy_change_percent: -5.5,
          on_track: true,
        },
        emissions_breakdown: {
          scope_1: { value: 10, label: 'Direct' },
          scope_2: { value: 5, label: 'Indirect' },
          scope_3: { value: 7.1, label: 'Value Chain' },
        },
        data_quality: { scope_1_2: 12, scope_3: 10, target: 12 },
        certification: { status: 'in_progress', expiry_date: null },
        actions: { total: 2, completed: 1, overdue: 0 },
        targets: { reduction_percent: 5, target_per_fte: 1.0 },
        historical_years: [{ label: 'YE2026', total: 22.1, per_fte: 1.1 }],
      },
    })
    mockListYears.mockResolvedValue({
      data: {
        total: 1,
        years: [
          {
            id: 1,
            year_label: 'YE2026',
            year_number: 2026,
            period: '01 Jan 2026 - 31 Dec 2026',
            average_fte: 20,
            total_emissions: 22.1,
            emissions_per_fte: 1.1,
            scope_1: 10,
            scope_2_market: 5,
            scope_3: 7.1,
            data_quality: 12,
            certification_status: 'in_progress',
            is_baseline: false,
          },
        ],
      },
    })
    mockListSources.mockResolvedValue({
      data: {
        year_id: 1,
        total_co2e: 22.1,
        sources: [
          {
            id: 1,
            source_name: 'Fleet Diesel',
            source_category: 'fuel',
            scope: 'scope_1',
            activity_value: 100,
            activity_unit: 'litres',
            co2e_tonnes: 10,
            percentage: 45.2,
            data_quality: 'actual',
          },
        ],
      },
    })
    mockListActions.mockResolvedValue({
      data: {
        year_id: 1,
        summary: { total: 1, completed: 1, in_progress: 0, overdue: 0, completion_rate: 100 },
        actions: [
          {
            id: 1,
            action_id: 'ACT-001',
            action_title: 'Install smart meter',
            owner: 'Ops',
            deadline: '2026-06-01T00:00:00Z',
            scheduled_month: 'Jun 26',
            status: 'completed',
            progress_percent: 100,
            is_overdue: false,
          },
        ],
      },
    })
    mockGetScope3.mockResolvedValue({
      data: {
        year_id: 1,
        measured_count: 1,
        total_co2e: 7.1,
        categories: [{ number: 1, name: 'Purchased goods', is_measured: true, total_co2e: 7.1, percentage: 100 }],
      },
    })
    mockGetCertification.mockResolvedValue({
      data: {
        year_id: 1,
        year_label: 'YE2026',
        status: 'in_progress',
        certificate_number: null,
        certification_date: null,
        expiry_date: null,
        readiness_percent: 80,
        evidence_checklist: [
          { type: 'utility_bill', category: 'scope_2', description: 'Electricity bills', required: true, uploaded: true, verified: true },
        ],
        actions_completed: 1,
        actions_total: 1,
        data_quality_met: true,
        next_steps: [],
      },
    })
    mockGetDataQuality.mockResolvedValue({
      data: {
        year_id: 1,
        overall_score: 12,
        max_score: 16,
        scopes: {
          scope_1: { score: 6, actual_pct: 100, recommendations: [] },
          scope_2: { score: 6, actual_pct: 100, recommendations: [] },
          scope_3: { score: 10, actual_pct: 80, recommendations: ['Engage suppliers'] },
        },
        priority_improvements: [{ action: 'Engage suppliers', impact: '+2 points' }],
        target_scores: {},
      },
    })
  })

  it('renders live Planet Mark data from the aligned API envelopes', async () => {
    const PlanetMark = (await import('../PlanetMark')).default

    render(<PlanetMark />)

    expect(await screen.findByText('YE2026')).toBeInTheDocument()
    expect(await screen.findByText('Fleet Diesel')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockListActions).toHaveBeenCalledWith(1)
      expect(mockGetCertification).toHaveBeenCalledWith(1)
    })
  })
})
