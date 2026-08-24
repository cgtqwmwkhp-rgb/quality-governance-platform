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
    t: (key: string) => {
      const labels: Record<string, string> = {
        'ims.shell.section.overview': 'Overview',
        'ims.shell.section.mapping': 'Cross-Standard Mapping',
        'ims.shell.section.audit': 'Unified Audit Plan',
        'ims.shell.section.review': 'Management Review',
        'ims.shell.section.isms': 'ISO 27001 ISMS',
        'ims.shell.tabs_aria': 'IMS sections',
      }
      return labels[key] ?? key
    },
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

const cellOverviewFixture = {
  tracked_count: 7,
  matrix_loaded: false,
  matrix_version: null,
  totals: { covered: 2, partial: 1, gap: 1, unknown: 81, cells: 85 },
  frameworks: [
    {
      framework: 'ce',
      axis_source: 'requirement_catalogue',
      cells: 5,
      covered: 1,
      partial: 0,
      gap: 0,
      unknown: 4,
      cert_count: 1,
      open_nc_cells: 0,
    },
    {
      framework: 'uvdb',
      axis_source: 'requirement_catalogue',
      cells: 46,
      covered: 0,
      partial: 1,
      gap: 1,
      unknown: 44,
      cert_count: 0,
      open_nc_cells: 1,
    },
    {
      framework: 'pm',
      axis_source: 'requirement_catalogue',
      cells: 4,
      covered: 1,
      partial: 0,
      gap: 0,
      unknown: 3,
      cert_count: 1,
      open_nc_cells: 0,
    },
  ],
  scan_truncated: false,
  scan_truncated_sources: [],
  honesty: 'Counts of matrix cells — not a compliance percentage.',
}

const dashboardFixture = {
  generated_at: '2026-07-13T00:00:00Z',
  overall_compliance: 82,
  cell_overview: cellOverviewFixture,
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
    expect(mockNavigate).toHaveBeenCalledWith('/compliance?view=matrix')

    await user.click(screen.getByTestId('compliance-hub-evidence'))
    expect(mockNavigate).toHaveBeenCalledWith('/compliance?view=evidence')

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

  it('meters IMS Overview from cell aggregate, not Control-table implementation %', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('ims-metric-cell-overview')).toBeInTheDocument()
    })

    expect(screen.getByTestId('ims-metric-frameworks-tracked')).toHaveTextContent('7')
    expect(screen.getByTestId('ims-frameworks-tracked-badge')).toBeInTheDocument()
    expect(screen.getByTestId('ims-metric-cells-covered')).toHaveTextContent('2')
    expect(screen.queryByTestId('ims-metric-control-implementation')).not.toBeInTheDocument()
    expect(screen.queryByText('82%')).not.toBeInTheDocument()
    expect(screen.queryByText(/Control implementation — live from management system controls/i)).not.toBeInTheDocument()
    expect(screen.getByTestId('ims-overview-framework-meters')).toBeInTheDocument()
    expect(screen.getByTestId('ims-overview-fw-uvdb')).toBeInTheDocument()
    expect(screen.getByTestId('ims-overview-fw-pm')).toBeInTheDocument()
  })

  it('still shows frameworks tracked when the Control table is empty', async () => {
    mockGetDashboard.mockResolvedValue({
      data: {
        ...dashboardFixture,
        overall_compliance: 0,
        standards: [],
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
      expect(screen.getByTestId('ims-metric-frameworks-tracked')).toHaveTextContent('7')
    })
    expect(screen.getByTestId('ims-frameworks-tracked-badge')).toBeInTheDocument()
  })

  it('shows live overview KPIs and audit-schedule activity without demo feed', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('ims-overview-kpi-honesty')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ims-overview-activity-honesty')).toBeInTheDocument()
    expect(screen.queryByText(/Minor NC #2024-015/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Open Actions/i)).not.toBeInTheDocument()
    expect(screen.getByText('Open scheduled audits')).toBeInTheDocument()
    expect(screen.getByText(/AUD-2026-042/i)).toBeInTheDocument()
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

  it('renders Audits-style section pills with default overview section', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')

    render(
      <MemoryRouter initialEntries={['/ims']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('ims-section-overview')).toBeInTheDocument()
    })

    expect(screen.getByRole('tab', { name: /Overview/i })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('ims-section-filter')).toBeInTheDocument()
  })

  it('routes ?section=mapping to cross-standard mapping panel', async () => {
    const { default: IMSDashboard } = await import('../IMSDashboard')

    render(
      <MemoryRouter initialEntries={['/ims?section=mapping']}>
        <Routes>
          <Route path="/ims" element={<IMSDashboard />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('ims-section-mapping')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Cross-Standard Mapping/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByTestId('ims-map-w1-panel')).toBeInTheDocument()
  })

  it('routes compliance hub ISMS chip to ?section=isms', async () => {
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
      expect(screen.getByTestId('compliance-hub-isms')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('compliance-hub-isms'))

    expect(await screen.findByTestId('ims-section-isms')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /ISO 27001 ISMS/i })).toHaveAttribute('aria-selected', 'true')
  })
})
