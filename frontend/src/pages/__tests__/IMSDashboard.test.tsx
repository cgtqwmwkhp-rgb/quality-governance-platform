import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const mockNavigate = vi.fn()
const mockGetDashboard = vi.fn()
const mockListMappings = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  imsDashboardApi: {
    getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
  },
  crossStandardMappingsApi: {
    list: (...args: unknown[]) => mockListMappings(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

const dashboardFixture = {
  generated_at: '2026-07-13T00:00:00Z',
  overall_compliance: 82,
  standards: [
    {
      standard_id: 1,
      standard_code: 'ISO9001',
      standard_name: 'ISO 9001',
      full_name: 'Quality Management',
      version: '2015',
      total_controls: 10,
      implemented_count: 8,
      partial_count: 1,
      not_implemented_count: 1,
      compliance_percentage: 85,
      setup_required: false,
    },
    {
      standard_id: 2,
      standard_code: 'ISO14001',
      standard_name: 'ISO 14001',
      full_name: 'Environmental Management',
      version: '2015',
      total_controls: 8,
      implemented_count: 6,
      partial_count: 1,
      not_implemented_count: 1,
      compliance_percentage: 79,
      setup_required: false,
    },
  ],
  audit_schedule: [
    {
      id: 42,
      reference_number: 'AUD-2026-042',
      title: 'Integrated QMS audit',
      status: 'scheduled',
      scheduled_date: '2026-08-01T00:00:00Z',
      due_date: null,
    },
  ],
  isms: null,
}

describe('IMSDashboard IA W2 compliance hub', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    mockGetDashboard.mockReset()
    mockListMappings.mockReset()
    mockGetDashboard.mockResolvedValue({ data: dashboardFixture })
    mockListMappings.mockResolvedValue({ data: [] })
  })

  it('renders compliance hub orientation cards instead of per-standard score galleries', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Compliance hub')).toBeInTheDocument()
    })

    expect(screen.getByTestId('compliance-hub-standards')).toBeInTheDocument()
    expect(screen.getByTestId('compliance-hub-evidence')).toBeInTheDocument()
    expect(screen.getByTestId('compliance-hub-monitoring')).toBeInTheDocument()
    expect(screen.getByTestId('compliance-hub-isms')).toBeInTheDocument()
    expect(screen.getByText('ims.hub.monitoring.title')).toBeInTheDocument()
    expect(screen.queryByText('85%')).not.toBeInTheDocument()
  })

  it('routes hub cards to real compliance destinations', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('compliance-hub-standards')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('compliance-hub-standards'))
    expect(mockNavigate).toHaveBeenCalledWith('/standards')

    await user.click(screen.getByTestId('compliance-hub-evidence'))
    expect(mockNavigate).toHaveBeenCalledWith('/compliance')

    await user.click(screen.getByTestId('compliance-hub-monitoring'))
    expect(mockNavigate).toHaveBeenCalledWith('/compliance-automation')
  })

  it('fixes broken audit CTAs to real routes', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('tab', { name: /Unified Audit Plan/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /ims.plan_new_audit/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /ims.plan_new_audit/i }))
    expect(mockNavigate).toHaveBeenCalledWith('/audits')
    expect(mockNavigate).not.toHaveBeenCalledWith('/audits/new')

    const auditRow = screen.getByText('AUD-2026-042').closest('tr')
    expect(auditRow).not.toBeNull()
    await user.click(within(auditRow!).getByRole('button', { name: /Open audit AUD-2026-042/i }))
    expect(mockNavigate).toHaveBeenCalledWith('/audits/42/execute')
  })

  it('labels control implementation vs evidence coverage when both metrics are live', async () => {
    mockGetDashboard.mockResolvedValue({
      data: {
        ...dashboardFixture,
        compliance_coverage: {
          total_clauses: 20,
          covered_clauses: 15,
          coverage_percentage: 67,
          gaps: 5,
          total_evidence_links: 22,
        },
      },
    })

    const { default: IMSDashboard } = await import('../IMSDashboard')

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('ims-metric-control-implementation')).toBeInTheDocument()
    })

    expect(screen.getByTestId('ims-metric-evidence-coverage')).toBeInTheDocument()
    expect(screen.getByLabelText('82% control implementation')).toBeInTheDocument()
    expect(screen.getByLabelText('67% evidence coverage')).toBeInTheDocument()
    expect(screen.getByText('Control implementation')).toBeInTheDocument()
    expect(screen.getByText('Evidence coverage')).toBeInTheDocument()
  })

  it('labels single banner as control implementation when evidence coverage is absent', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByLabelText('82% control implementation')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('ims-metric-evidence-coverage')).not.toBeInTheDocument()
    expect(screen.getByText(/Control implementation — live from management system controls/i)).toBeInTheDocument()
  })

  it('shows MAP-W1 multi-scheme honesty on Cross-Standard Mapping tab', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('tab', { name: /Cross-Standard Mapping/i }))

    expect(await screen.findByTestId('ims-map-w1-panel')).toBeInTheDocument()
    expect(screen.getByTestId('ims-map-w1-honesty')).toBeInTheDocument()
    expect(screen.getByTestId('ims-map-w1-scheme-chips')).toBeInTheDocument()
    expect(screen.getByTestId('ims-map-w1-scheme-iso')).toBeInTheDocument()
    expect(screen.getByTestId('ims-map-w1-scheme-planet-mark')).toBeInTheDocument()
    expect(screen.getByTestId('ims-map-w1-scheme-uvdb')).toBeInTheDocument()
  })
})
