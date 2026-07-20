import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import Incidents from '../Incidents'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const mockList = vi.fn()
const mockCreate = vi.fn()

vi.mock('../../api/client', () => ({
  incidentsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
  },
  notificationsApi: {
    getDeliveryStatus: vi.fn().mockResolvedValue({ data: { email_configured: false } }),
  },
  workforceApi: {
    listEngineers: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../components/EngineerPeoplePicker', () => ({
  EngineerPeoplePicker: () => <input data-testid="engineer-people-picker" />,
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

const mockResolveReporter = vi.fn()

vi.mock('../../utils/platformSessionReporter', () => ({
  resolvePlatformReporterIdentity: (...args: unknown[]) => mockResolveReporter(...args),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

const sampleIncidents = [
  {
    id: 1,
    reference_number: 'INC-001',
    title: 'Slip in warehouse',
    description: 'Worker slipped on wet floor',
    incident_type: 'injury',
    severity: 'high',
    status: 'reported',
    incident_date: '2026-02-15T10:00:00Z',
    reported_date: '2026-02-15T11:00:00Z',
    created_at: '2026-02-15T11:00:00Z',
  },
  {
    id: 2,
    reference_number: 'INC-002',
    title: 'Chemical spill in lab',
    description: 'Minor chemical spill near workstation',
    incident_type: 'environmental',
    severity: 'medium',
    status: 'under_investigation',
    incident_date: '2026-02-20T14:30:00Z',
    reported_date: '2026-02-20T15:00:00Z',
    created_at: '2026-02-20T15:00:00Z',
  },
]

const paginatedResponse = {
  data: {
    items: sampleIncidents,
    total: 2,
    page: 1,
    page_size: 50,
    total_pages: 1,
  },
}

describe('Incidents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue(paginatedResponse)
    mockResolveReporter.mockResolvedValue({
      reporter_name: 'Alex Engineer',
      reporter_email: 'alex@example.com',
    })
    mockCreate.mockResolvedValue({
      data: {
        id: 3,
        reference_number: 'INC-003',
        title: '',
        description: '',
        incident_type: 'other',
        severity: 'medium',
        status: 'reported',
        incident_date: new Date().toISOString(),
        reported_date: new Date().toISOString(),
        created_at: new Date().toISOString(),
      },
    })
  })

  it('renders loading state initially', () => {
    mockList.mockReturnValue(new Promise(() => {}))
    const { container } = render(<Incidents />, { wrapper: Wrapper })

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
    expect(screen.getByText('incidents.title')).toBeInTheDocument()
  })

  it('renders incident list after data loads', async () => {
    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    expect(screen.getByText('Slip in warehouse')).toBeInTheDocument()
    expect(screen.getByText('INC-002')).toBeInTheDocument()
    expect(screen.getByText('Chemical spill in lab')).toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(1, 50, undefined)
  })

  it('shows create form when button is clicked', async () => {
    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    const newButton = screen.getByText('incidents.new')
    fireEvent.click(newButton)

    await waitFor(() => {
      expect(screen.getByText('incidents.dialog.title')).toBeInTheDocument()
    })
    expect(screen.getByText('incidents.form.title')).toBeInTheDocument()
    expect(screen.getByText('incidents.form.description')).toBeInTheDocument()
  })

  it('handles API errors on load and shows error banner', async () => {
    mockList.mockRejectedValue(new Error('Server unavailable'))

    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('Server unavailable')).toBeInTheDocument()
    })

    const { trackError } = await import('../../utils/errorTracker')
    expect(trackError).toHaveBeenCalled()
  })

  it('creates an incident via the form', async () => {
    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('incidents.new'))

    await waitFor(() => {
      expect(screen.getByText('incidents.dialog.title')).toBeInTheDocument()
    })

    const titleInput = screen.getByPlaceholderText('incidents.form.title_placeholder')
    const descInput = screen.getByPlaceholderText('incidents.form.description_placeholder')

    fireEvent.change(titleInput, { target: { value: 'New incident' } })
    fireEvent.change(descInput, { target: { value: 'Detailed description' } })

    const submitButton = screen.getByText('incidents.create')
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledTimes(1)
    })

    const callArgs = mockCreate.mock.calls[0][0]
    expect(callArgs.title).toBe('New incident')
    expect(callArgs.description).toBe('Detailed description')
    expect(callArgs.reporter_name).toBe('Alex Engineer')
    expect(callArgs.reporter_email).toBe('alex@example.com')
  })

  it('shows session reporter hint when create modal opens (PX-015)', async () => {
    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('incidents.new'))

    await waitFor(() => {
      expect(screen.getByTestId('incident-create-reporter')).toHaveTextContent('Alex Engineer')
    })
  })

  it('decodes HTML entities in list titles (PX-009)', async () => {
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            ...sampleIncidents[0],
            title: 'Tools &amp; equipment',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        total_pages: 1,
      },
    })

    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('Tools & equipment')).toBeInTheDocument()
    })
  })

  it('shows error when creation fails', async () => {
    mockCreate.mockRejectedValue(new Error('Validation failed'))

    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('incidents.new'))

    await waitFor(() => {
      expect(screen.getByText('incidents.dialog.title')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText('incidents.form.title_placeholder'), {
      target: { value: 'Bad incident' },
    })
    fireEvent.change(screen.getByPlaceholderText('incidents.form.description_placeholder'), {
      target: { value: 'Some description' },
    })

    fireEvent.click(screen.getByText('incidents.create'))

    await waitFor(() => {
      expect(screen.getByText('Validation failed')).toBeInTheDocument()
    })
  })

  it('filters incidents via search', async () => {
    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    expect(screen.getByText('Chemical spill in lab')).toBeInTheDocument()

    const searchInput = screen.getByPlaceholderText('incidents.search_placeholder')
    fireEvent.change(searchInput, { target: { value: 'warehouse' } })

    expect(screen.getByText('Slip in warehouse')).toBeInTheDocument()
    expect(screen.queryByText('Chemical spill in lab')).not.toBeInTheDocument()
  })

  it('navigates to incident detail when a row is clicked', async () => {
    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    const rows = screen.getAllByTestId('incident-row-link')
    fireEvent.click(rows[0])

    expect(mockNavigate).toHaveBeenCalledWith('/incidents/1')
  })

  it('opens incident detail when row receives Enter (PX-008)', async () => {
    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    const row = screen.getAllByTestId('incident-row-link')[0]
    fireEvent.keyDown(row, { key: 'Enter' })

    expect(mockNavigate).toHaveBeenCalledWith('/incidents/1')
  })

  it('shows pagination when total exceeds page size (PX-004)', async () => {
    mockList.mockResolvedValue({
      data: {
        items: sampleIncidents,
        total: 120,
        page: 1,
        page_size: 50,
        pages: 3,
      },
    })

    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByTestId('incidents-pagination')).toBeInTheDocument()
    })
    expect(screen.getByText('common.previous')).toBeInTheDocument()
    expect(screen.getByText('common.next')).toBeInTheDocument()
    expect(screen.getByText('a11y.page_of')).toBeInTheDocument()
  })

  it('shows search scope honesty when filtering current page (PX-004)', async () => {
    render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText('incidents.search_placeholder'), {
      target: { value: 'warehouse' },
    })

    expect(screen.getByTestId('incidents-search-scope-honesty')).toBeInTheDocument()
  })

  it('hydrates q/status/severity filters from shareable URL', async () => {
    render(
      <MemoryRouter initialEntries={['/incidents?q=warehouse&status=reported&severity=high']}>
        <Routes>
          <Route path="/incidents" element={<Incidents />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    expect(screen.getByPlaceholderText('incidents.search_placeholder')).toHaveValue('warehouse')
    expect(screen.queryByText('Chemical spill in lab')).not.toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(1, 50, undefined)
  })

  it('renders rows with null type/status/date without crashing (ErrorBoundary honesty)', async () => {
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 9,
            reference_number: 'INC-NULL',
            title: 'Sparse row',
            description: 'Missing enums',
            incident_type: null,
            severity: null,
            status: null,
            incident_date: null,
            reported_date: '2026-02-15T11:00:00Z',
            created_at: '2026-02-15T11:00:00Z',
          },
          null,
          { id: 'bad' },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        total_pages: 1,
      },
    })

    // Clean MemoryRouter — BrowserRouter inherits ?q= from earlier list tests.
    render(
      <MemoryRouter initialEntries={['/incidents']}>
        <Routes>
          <Route path="/incidents" element={<Incidents />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('INC-NULL')).toBeInTheDocument()
    })
    expect(screen.getByText('Sparse row')).toBeInTheDocument()
    // humanizeToken / formatIncidentDate fall back to em dash — at least one cell
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('treats non-array items as empty list with honesty banner', async () => {
    mockList.mockResolvedValue({
      data: { items: { unexpected: true }, total: 0, page: 1, page_size: 50 },
    })

    render(
      <MemoryRouter initialEntries={['/incidents']}>
        <Routes>
          <Route path="/incidents" element={<Incidents />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByText(/Incident list returned an unexpected shape/i),
      ).toBeInTheDocument()
    })
    expect(screen.getByText('incidents.empty.title')).toBeInTheDocument()
  })
})
