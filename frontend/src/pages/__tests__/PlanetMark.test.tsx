import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PlanetMark from '../PlanetMark'

const mockGetDashboard = vi.fn()
const mockListYears = vi.fn()
const mockListActions = vi.fn()
const mockGetActionsSummary = vi.fn()
const mockCreateReportingYear = vi.fn()
const mockCreateApiError = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { year?: string }) => {
      if (key === 'planet_mark.shell.export_ready' && opts?.year) {
        return `Export ready for ${opts.year}`
      }
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  planetMarkApi: {
    getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
    listYears: (...args: unknown[]) => mockListYears(...args),
    createReportingYear: (...args: unknown[]) => mockCreateReportingYear(...args),
    listActions: (...args: unknown[]) => mockListActions(...args),
    getActionsSummary: (...args: unknown[]) => mockGetActionsSummary(...args),
  },
  ErrorClass: {
    NETWORK_ERROR: 'NETWORK_ERROR',
    SERVER_ERROR: 'SERVER_ERROR',
    AUTH_ERROR: 'AUTH_ERROR',
    NOT_FOUND: 'NOT_FOUND',
    UNKNOWN: 'UNKNOWN',
  },
  createApiError: (...args: unknown[]) => mockCreateApiError(...args),
  isSetupRequired: (payload: Record<string, unknown>) => payload?.error_class === 'SETUP_REQUIRED',
}))

vi.mock('../../components/ui/SetupRequiredPanel', () => ({
  SetupRequiredPanel: ({ response }: { response: { message: string } }) => <div>{response.message}</div>,
}))

vi.mock('../../components/planet-mark/ActionCard', () => ({
  ActionCard: ({ action }: { action: { action_title: string } }) => <div>{action.action_title}</div>,
}))

vi.mock('../../components/planet-mark/ActionSummaryKPIs', () => ({
  ActionSummaryKPIs: () => <div data-testid="action-summary-kpis" />,
}))

const yearRecord = {
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
}

function renderPlanetMark(initialEntry = '/planet-mark') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PlanetMark />
    </MemoryRouter>,
  )
}

describe('PlanetMark shell', () => {
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
        actions: { total: 0, completed: 0, overdue: 0 },
        targets: { reduction_percent: 5, target_per_fte: 1.0 },
        historical_years: [{ label: 'YE2026', total: 22.1, per_fte: 1.1 }],
      },
    })
    mockListYears.mockResolvedValue({ data: { total: 1, years: [yearRecord] } })
    mockListActions.mockResolvedValue({ data: { year_id: 1, summary: {}, actions: [] } })
    mockGetActionsSummary.mockResolvedValue({
      data: {
        year_id: 1,
        total: 0,
        completed: 0,
        in_progress: 0,
        overdue: 0,
        not_started: 0,
        completion_rate_percent: 0,
        avg_progress_percent: 0,
      },
    })
    mockCreateReportingYear.mockResolvedValue({ data: { id: 2, year_label: 'YE2026', message: 'ok' } })
    mockCreateApiError.mockReturnValue({ error_class: 'UNKNOWN' })
  })

  it('renders Audits-style section tabs and year switcher with live year data', async () => {
    renderPlanetMark('/planet-mark?year=1')

    expect(await screen.findByText('planet_mark.title')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /planet_mark.shell.section.years/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByLabelText('planet_mark.shell.year_switcher_label')).toHaveValue('1')
    expect(await screen.findByTestId('planet-mark-section-years')).toBeInTheDocument()
    expect(screen.getByText('22.1')).toBeInTheDocument()
  })

  it('shows honest empty state on monthly section (no ingest API)', async () => {
    renderPlanetMark('/planet-mark?year=1&section=monthly')

    expect(await screen.findByTestId('planet-mark-section-monthly')).toBeInTheDocument()
    expect(screen.getByText('planet_mark.shell.empty.monthly')).toBeInTheDocument()
    expect(screen.getByText('planet_mark.shell.empty.monthly_desc')).toBeInTheDocument()
  })

  it('shows honest empty improve state when actions API returns none', async () => {
    renderPlanetMark('/planet-mark?year=1&section=improve')

    expect(await screen.findByTestId('planet-mark-section-improve')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockListActions).toHaveBeenCalledWith(1)
    })
    expect(screen.getByText('planet_mark.shell.empty.improve')).toBeInTheDocument()
  })

  it('renders live improvement actions when API returns rows', async () => {
    mockListActions.mockResolvedValue({
      data: {
        year_id: 1,
        summary: { total: 1, completed: 0, in_progress: 1, overdue: 0, completion_rate: 0 },
        actions: [
          {
            id: 1,
            action_id: 'ACT-001',
            action_title: 'Install smart meter',
            owner: 'Ops',
            deadline: '2026-06-01T00:00:00Z',
            scheduled_month: 'Jun 26',
            status: 'in_progress',
            progress_percent: 40,
            is_overdue: false,
          },
        ],
      },
    })

    renderPlanetMark('/planet-mark?year=1&section=improve')

    expect(await screen.findByText('Install smart meter')).toBeInTheDocument()
    expect(screen.getByTestId('action-summary-kpis')).toBeInTheDocument()
  })

  it('shows trends table when dashboard historical years exist', async () => {
    renderPlanetMark('/planet-mark?year=1&section=trends')

    const section = await screen.findByTestId('planet-mark-section-trends')
    expect(section).toBeInTheDocument()
    expect(section.querySelector('tbody')?.textContent).toContain('YE2026')
  })

  it('shows honest trends empty when no historical years', async () => {
    mockGetDashboard.mockResolvedValue({
      data: {
        current_year: {
          id: 1,
          label: 'YE2026',
          total_emissions: 0,
          emissions_per_fte: 0,
          fte: 1,
          yoy_change_percent: null,
          on_track: false,
        },
        emissions_breakdown: {
          scope_1: { value: 0, label: 'Direct' },
          scope_2: { value: 0, label: 'Indirect' },
          scope_3: { value: 0, label: 'Value Chain' },
        },
        data_quality: { scope_1_2: 0, scope_3: 0, target: 12 },
        certification: { status: 'draft', expiry_date: null },
        actions: { total: 0, completed: 0, overdue: 0 },
        targets: { reduction_percent: null, target_per_fte: null },
        historical_years: [],
      },
    })

    renderPlanetMark('/planet-mark?year=1&section=trends')

    expect(await screen.findByText('planet_mark.shell.empty.trends')).toBeInTheDocument()
  })

  it('exposes export section for selected year', async () => {
    renderPlanetMark('/planet-mark?year=1&section=export')

    expect(await screen.findByTestId('planet-mark-section-export')).toBeInTheDocument()
    expect(screen.getByText('Export ready for YE2026')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /planet_mark.export_report/i })).toBeInTheDocument()
  })

  it('allows first-time setup by creating a reporting year', async () => {
    mockGetDashboard
      .mockResolvedValueOnce({
        data: {
          error_class: 'SETUP_REQUIRED',
          setup_required: true,
          module: 'planet-mark',
          message: 'No carbon reporting years configured',
          next_action: 'Create a reporting year via POST /api/v1/planet-mark/years',
        },
      })
      .mockResolvedValue({
        data: {
          current_year: {
            id: 1,
            label: 'YE2026',
            total_emissions: 22.1,
            emissions_per_fte: 1.1,
            fte: 20,
            yoy_change_percent: null,
            on_track: true,
          },
          emissions_breakdown: {
            scope_1: { value: 10, label: 'Direct' },
            scope_2: { value: 5, label: 'Indirect' },
            scope_3: { value: 7.1, label: 'Value Chain' },
          },
          data_quality: { scope_1_2: 12, scope_3: 10, target: 12 },
          certification: { status: 'in_progress', expiry_date: null },
          actions: { total: 0, completed: 0, overdue: 0 },
          targets: { reduction_percent: 5, target_per_fte: 1.0 },
          historical_years: [],
        },
      })
    mockListYears
      .mockResolvedValueOnce({
        data: {
          error_class: 'SETUP_REQUIRED',
          setup_required: true,
          module: 'planet-mark',
          message: 'No carbon reporting years configured',
          next_action: 'Create a reporting year via POST /api/v1/planet-mark/years',
        },
      })
      .mockResolvedValue({ data: { total: 1, years: [yearRecord] } })

    renderPlanetMark()

    expect(await screen.findByText('No carbon reporting years configured')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'planet_mark.shell.setup.submit' }))

    await waitFor(() => {
      expect(mockCreateReportingYear).toHaveBeenCalledWith(
        expect.objectContaining({
          year_label: 'YE2026',
          year_number: 2026,
          average_fte: 1,
        }),
      )
    })
  })
})
