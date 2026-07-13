import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import ComplaintDetail from '../ComplaintDetail'

const mockNavigate = vi.fn()
const mockToastError = vi.fn()
const mockToastSuccess = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | Record<string, unknown>) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === 'object' && 'defaultValue' in fallbackOrOptions) {
        return String(fallbackOrOptions.defaultValue)
      }
      return key
    },
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

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
    success: (...args: unknown[]) => mockToastSuccess(...args),
  },
}))

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
    mockToastError.mockReset()
    mockToastSuccess.mockReset()
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

  it('shows toast when save edit fails', async () => {
    client.complaintsApi.update.mockRejectedValue(new Error('Invalid status transition'))
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Late repairs response' })).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: 'edit' }))
    await userEvent.click(screen.getByTestId('complaint-save-edit'))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Invalid status transition')
    })
  })

  it('investigation modal only collects title (API contract honest)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('complaint-start-investigation')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByTestId('complaint-start-investigation'))

    expect(screen.getByTestId('complaint-investigation-modal')).toBeInTheDocument()
    expect(screen.getByTestId('complaint-investigation-title')).toBeInTheDocument()
    expect(screen.queryByText(/investigation type/i)).not.toBeInTheDocument()
    expect(screen.queryByTestId('user-email-search')).not.toBeInTheDocument()
  })

  it('stays on complaint detail after investigation create and reloads list', async () => {
    client.investigationsApi.createFromRecord.mockResolvedValue({
      data: { id: 26, reference_number: 'INV-26', title: 'New investigation' },
    })
    client.complaintsApi.listInvestigations
      .mockResolvedValueOnce({ data: { items: [], total: 0 } })
      .mockResolvedValueOnce({
        data: { items: [{ id: 26, reference_number: 'INV-26', title: 'New investigation' }], total: 1 },
      })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('complaint-start-investigation')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByTestId('complaint-start-investigation'))
    await userEvent.type(screen.getByTestId('complaint-investigation-title'), 'Root cause review')
    await userEvent.click(screen.getByRole('button', { name: 'complaints.detail.create_investigation' }))

    await waitFor(() => {
      expect(client.investigationsApi.createFromRecord).toHaveBeenCalledWith({
        source_type: 'complaint',
        source_id: 15,
        title: 'Root cause review',
      })
    })

    expect(mockNavigate).not.toHaveBeenCalledWith('/investigations')
    expect(mockToastSuccess).toHaveBeenCalled()
    await waitFor(() => {
      expect(client.complaintsApi.listInvestigations).toHaveBeenCalledTimes(2)
    })
  })

  it('shows honest key dates card instead of activity timeline label', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('complaint-key-dates')).toBeInTheDocument()
    })

    expect(screen.getByText('Key dates')).toBeInTheDocument()
    expect(screen.getByText(/Running Sheet tab/i)).toBeInTheDocument()
    expect(screen.queryByText('complaints.detail.activity_timeline')).not.toBeInTheDocument()
  })
})
