import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import IncidentDetail from '../IncidentDetail'

const mockNavigate = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | Record<string, unknown>) =>
      typeof fallbackOrOptions === 'string' ? fallbackOrOptions : key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: '11' }),
  }
})

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../components/ui/Breadcrumbs', () => ({
  Breadcrumbs: () => <div data-testid="breadcrumbs" />,
}))

vi.mock('../../components/UserEmailSearch', () => ({
  UserEmailSearch: () => <div data-testid="user-email-search" />,
}))

vi.mock('../../components/ui/Tabs', () => ({
  Tabs: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsTrigger: ({ children }: { children: ReactNode }) => <button type="button">{children}</button>,
  TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock('../../api/client', () => ({
  incidentsApi: {
    get: vi.fn(),
    update: vi.fn(),
    listInvestigations: vi.fn(),
    listRunningSheet: vi.fn(),
    addRunningSheetEntry: vi.fn(),
    deleteRunningSheetEntry: vi.fn(),
  },
  investigationsApi: {
    createFromRecord: vi.fn(),
  },
  actionsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
  getApiErrorMessage: (err: Error) => err.message,
}))

const incidentRecord = {
  id: 11,
  reference_number: 'INC-11',
  title: 'Loader slip',
  description: 'A colleague slipped on a wet access point.',
  incident_type: 'injury',
  severity: 'high',
  status: 'reported',
  incident_date: '2026-03-12T09:45:00Z',
  location: 'North gate',
  department: 'Facilities',
  reported_date: '2026-03-12T10:00:00Z',
  created_at: '2026-03-12T10:05:00Z',
  updated_at: '2026-03-12T10:05:00Z',
  reporter_name: 'Alice Reporter',
  reporter_email: 'alice@example.com',
  people_involved: 'Bob Worker',
  first_aid_given: true,
  emergency_services_called: true,
  reporter_submission: {
    contract: 'facilities',
    person_name: 'Bob Worker',
    person_role: 'Cleaner',
    witness_names: 'Jane Witness',
    medical_assistance: 'ambulance',
    has_injuries: true,
    photos: { count: 2 },
  },
}

function renderPage() {
  return render(
    <BrowserRouter>
      <IncidentDetail />
    </BrowserRouter>,
  )
}

describe('IncidentDetail', () => {
  let client: Awaited<typeof import('../../api/client')>

  beforeEach(async () => {
    vi.clearAllMocks()
    mockNavigate.mockReset()
    client = await import('../../api/client')
    client.incidentsApi.get.mockResolvedValue({ data: incidentRecord })
    client.incidentsApi.listInvestigations.mockResolvedValue({
      data: { items: [{ id: 21, reference_number: 'INV-21', title: 'Linked investigation' }], total: 1 },
    })
    client.incidentsApi.listRunningSheet.mockResolvedValue({ data: [] })
    client.actionsApi.list.mockResolvedValue({
      data: { items: [{ id: 1, title: 'Secure CCTV', status: 'open' }] },
    })
  })

  it('surfaces reporter, impact, and submission details on first view', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    expect(screen.getAllByText('Alice Reporter').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Bob Worker').length).toBeGreaterThan(0)
    expect(screen.getAllByText('2 uploaded').length).toBeGreaterThan(0)
    expect(screen.getAllByText('INV-21').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Jane Witness').length).toBeGreaterThan(0)
    expect(screen.getAllByText('ambulance').length).toBeGreaterThan(0)
  })
})
