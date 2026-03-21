import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import RTADetail from '../RTADetail'

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
    useParams: () => ({ id: '42' }),
  }
})

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../components/ui/Breadcrumbs', () => ({
  Breadcrumbs: () => <div data-testid="breadcrumbs" />,
}))

vi.mock('../../components/ui/Tabs', () => ({
  Tabs: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsTrigger: ({ children }: { children: ReactNode }) => <button type="button">{children}</button>,
  TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock('../../api/client', () => ({
  rtasApi: {
    get: vi.fn(),
    listRunningSheet: vi.fn(),
    update: vi.fn(),
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
  evidenceAssetsApi: {
    list: vi.fn(),
    upload: vi.fn(),
    delete: vi.fn(),
  },
  getApiErrorMessage: (err: Error) => err.message,
}))

const mockRta = {
  id: 42,
  reference_number: 'RTA-42',
  title: 'Fleet collision',
  description: 'Minor road traffic incident',
  severity: 'high',
  status: 'open',
  collision_date: '2026-03-01',
  reported_date: '2026-03-02',
  location: 'A1',
  driver_injured: false,
  police_attended: false,
  insurance_notified: false,
  third_parties: {
    parties: [
      {
        vehicle_reg: 'AB12 CDE',
        vehicle_make_model: 'VW Polo',
        damage: 'Front bumper damage',
        insurer: 'Acme Insurance',
        insurer_policy_number: 'POL-123',
        name: 'Jane Driver',
        phone: '07000000000',
        email: 'jane@example.com',
        injured: true,
        injury_details: 'Whiplash',
      },
    ],
  },
  witnesses_structured: {
    witnesses: [
      {
        name: 'John Witness',
        phone: '07111111111',
        email: 'john@example.com',
        willing_to_provide_statement: true,
        statement: 'Observed the vehicle stop suddenly.',
      },
    ],
  },
  created_at: '2026-03-02T10:00:00Z',
}

function renderPage() {
  return render(
    <BrowserRouter>
      <RTADetail />
    </BrowserRouter>,
  )
}

describe('RTADetail', () => {
  let client: Awaited<typeof import('../../api/client')>

  beforeEach(async () => {
    vi.clearAllMocks()
    mockNavigate.mockReset()
    client = await import('../../api/client')

    client.rtasApi.get.mockResolvedValue({ data: mockRta })
    client.rtasApi.listRunningSheet.mockResolvedValue({ data: [] })
    client.actionsApi.list.mockResolvedValue({ data: { items: [] } })
    client.evidenceAssetsApi.list.mockResolvedValue({ data: { items: [] } })
  })

  it('associates dynamic edit labels with third-party and witness controls', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Fleet collision' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    expect(screen.getAllByLabelText('Registration').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByLabelText('Make / Model').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByLabelText('Damage').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByLabelText('Insurer')).toBeInTheDocument()
    expect(screen.getByLabelText('Policy No.')).toBeInTheDocument()

    expect(screen.getAllByLabelText('Name').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByLabelText('Phone').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByLabelText('Email').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByLabelText('Injured')).toBeInTheDocument()
    expect(screen.getByLabelText('Injury Details')).toBeInTheDocument()

    expect(screen.getByLabelText('Willing to give statement')).toBeInTheDocument()
    expect(screen.getByLabelText('Statement')).toBeInTheDocument()
  })
})
