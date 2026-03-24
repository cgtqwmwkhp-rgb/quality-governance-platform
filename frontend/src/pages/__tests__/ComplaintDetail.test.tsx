import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import ComplaintDetail from '../ComplaintDetail'

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
    useParams: () => ({ id: '15' }),
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
  complaintsApi: {
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

const complaintRecord = {
  id: 15,
  reference_number: 'COMP-15',
  title: 'Late repairs response',
  description: 'The operative did not arrive when promised.',
  complaint_type: 'service',
  priority: 'high',
  status: 'received',
  received_date: '2026-03-10T08:30:00Z',
  complainant_name: 'Carol Customer',
  complainant_email: 'carol@example.com',
  complainant_phone: '07000000000',
  department: 'Responsive Repairs',
  resolution_summary: null,
  created_at: '2026-03-10T08:35:00Z',
  updated_at: '2026-03-10T08:35:00Z',
  reporter_submission: {
    contract: 'responsive_repairs',
    complainant_name: 'Carol Customer',
    complainant_role: 'Resident',
    complainant_contact: '07000000000',
    location: 'Block A',
    photos: { count: 1 },
  },
}

function renderPage() {
  return render(
    <BrowserRouter>
      <ComplaintDetail />
    </BrowserRouter>,
  )
}

describe('ComplaintDetail', () => {
  let client: Awaited<typeof import('../../api/client')>

  beforeEach(async () => {
    vi.clearAllMocks()
    mockNavigate.mockReset()
    client = await import('../../api/client')
    client.complaintsApi.get.mockResolvedValue({ data: complaintRecord })
    client.complaintsApi.listInvestigations.mockResolvedValue({
      data: { items: [{ id: 25, reference_number: 'INV-25', title: 'Complaint investigation' }], total: 1 },
    })
    client.complaintsApi.listRunningSheet.mockResolvedValue({ data: [] })
    client.actionsApi.list.mockResolvedValue({
      data: { items: [{ id: 3, title: 'Acknowledge complainant', status: 'open' }] },
    })
  })

  it('shows complainant briefing fields and preserved submission data', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Late repairs response' })).toBeInTheDocument()
    })

    expect(screen.getAllByText('Carol Customer').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Resident').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Responsive Repairs').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Block A').length).toBeGreaterThan(0)
    expect(screen.getAllByText('1 uploaded').length).toBeGreaterThan(0)
    expect(screen.getAllByText('INV-25').length).toBeGreaterThan(0)
  })
})
