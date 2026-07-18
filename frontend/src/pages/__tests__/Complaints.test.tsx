import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Complaints from '../Complaints'

const mockNavigate = vi.fn()
const mockToastError = vi.fn()
const mockToastSuccess = vi.fn()
const mockT = (key: string, fallbackOrOptions?: string | Record<string, unknown>) => {
  if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
  if (
    fallbackOrOptions &&
    typeof fallbackOrOptions === 'object' &&
    'defaultValue' in fallbackOrOptions
  ) {
    return String(fallbackOrOptions.defaultValue)
  }
  return key
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
    success: (...args: unknown[]) => mockToastSuccess(...args),
  },
}))

const mockList = vi.fn()
const mockCreate = vi.fn()
const mockGetDeliveryStatus = vi.fn()
const mockContractsList = vi.fn()
const mockLookupsList = vi.fn()
const mockEvidenceUpload = vi.fn()

vi.mock('../../api/client', () => ({
  complaintsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
  },
  notificationsApi: {
    getDeliveryStatus: (...args: unknown[]) => mockGetDeliveryStatus(...args),
  },
  contractsApi: {
    list: (...args: unknown[]) => mockContractsList(...args),
  },
  lookupsApi: {
    list: (...args: unknown[]) => mockLookupsList(...args),
  },
  evidenceAssetsApi: {
    upload: (...args: unknown[]) => mockEvidenceUpload(...args),
  },
  workforceApi: {
    listEngineers: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../components/EngineerPeoplePicker', () => ({
  EngineerPeoplePicker: ({
    valueLabel,
    onChange,
    placeholder,
  }: {
    valueLabel?: string
    onChange: (selection: null) => void
    placeholder?: string
  }) => (
    <input
      data-testid="engineer-people-picker"
      value={valueLabel || ''}
      placeholder={placeholder}
      onChange={() => onChange(null)}
    />
  ),
}))

vi.mock('../../components/UserEmailSearch', () => ({
  UserEmailSearch: ({
    value,
    onChange,
    label,
  }: {
    value: string
    onChange: (v: string) => void
    label?: string
  }) => (
    <label>
      {label}
      <input
        data-testid="user-email-search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  ),
}))

vi.mock('../../components/FuzzySearchDropdown', () => ({
  default: ({
    value,
    onChange,
    label,
    placeholder,
  }: {
    value: string
    onChange: (v: string) => void
    label?: string
    placeholder?: string
  }) => (
    <label>
      {label}
      <input
        data-testid={`fuzzy-${placeholder || label || 'search'}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  ),
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

const sampleComplaints = [
  {
    id: 1,
    reference_number: 'CMP-001',
    title: 'Late delivery issue',
    description: 'Package arrived two weeks late',
    complaint_type: 'delivery',
    priority: 'high',
    status: 'received',
    received_date: '2026-02-10T09:00:00Z',
    complainant_name: 'John Doe',
    complainant_email: 'john@example.com',
    complainant_phone: '',
  },
  {
    id: 2,
    reference_number: 'CMP-002',
    title: 'Billing overcharge',
    description: 'Charged twice for the same item',
    complaint_type: 'billing',
    priority: 'medium',
    status: 'under_investigation',
    received_date: '2026-02-18T14:00:00Z',
    complainant_name: 'Jane Smith',
    complainant_email: 'jane@example.com',
    complainant_phone: '07700900000',
  },
]

const paginatedResponse = {
  data: {
    items: sampleComplaints,
    total: 2,
    page: 1,
    page_size: 50,
    total_pages: 1,
  },
}

describe('Complaints', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue(paginatedResponse)
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: true } })
    mockContractsList.mockResolvedValue({
      items: [
        {
          id: 10,
          code: 'ACME',
          name: 'Acme Facilities',
          client_name: 'Acme Corp',
          is_active: true,
        },
      ],
      total: 1,
    })
    mockLookupsList.mockResolvedValue({ items: [], total: 0 })
    mockEvidenceUpload.mockResolvedValue({ data: { id: 1 } })
    mockCreate.mockResolvedValue({
      data: {
        id: 3,
        reference_number: 'CMP-003',
        title: 'New complaint',
        description: 'Detailed description',
        complaint_type: 'other',
        priority: 'medium',
        status: 'received',
        received_date: new Date().toISOString(),
        complainant_name: 'Jane Doe',
        complainant_email: '',
        complainant_phone: '',
        contract_id: 10,
        source_type: 'phone',
      },
    })
  })

  async function fillRequiredCreateFields() {
    fireEvent.change(screen.getByTestId('fuzzy-Search customer / contract…'), {
      target: { value: '10' },
    })
    fireEvent.change(screen.getByPlaceholderText('complaints.form.title_placeholder'), {
      target: { value: 'New complaint' },
    })
    fireEvent.change(screen.getByPlaceholderText('complaints.form.description_placeholder'), {
      target: { value: 'Detailed description' },
    })
    fireEvent.change(screen.getByPlaceholderText('complaints.form.name_placeholder'), {
      target: { value: 'Jane Doe' },
    })
  }

  it('renders loading state initially', () => {
    mockList.mockReturnValue(new Promise(() => {}))
    const { container } = render(<Complaints />, { wrapper: Wrapper })

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
    expect(screen.getByText('complaints.title')).toBeInTheDocument()
  })

  it('renders complaint list after data loads with live badge', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    expect(screen.getByText('Late delivery issue')).toBeInTheDocument()
    expect(screen.getByText('CMP-002')).toBeInTheDocument()
    expect(screen.getByText('Billing overcharge')).toBeInTheDocument()
    expect(screen.getByTestId('complaints-live-badge')).toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(1, 50, undefined)
  })

  it('renders page header and search input', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await screen.findByPlaceholderText('complaints.search_placeholder')

    expect(screen.getByText('complaints.subtitle')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('complaints.search_placeholder')).toBeInTheDocument()
    expect(screen.getByText('complaints.new')).toBeInTheDocument()
  })

  it('shows create form when button is clicked', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('complaints.new'))

    await waitFor(() => {
      expect(screen.getByText('complaints.dialog.title')).toBeInTheDocument()
    })
    expect(screen.getByText('complaints.form.title')).toBeInTheDocument()
    expect(screen.getByText('complaints.form.description')).toBeInTheDocument()
  })

  it('shows unavailable empty state (not fake empty) when list fails', async () => {
    mockList.mockRejectedValue(new Error('Server unavailable'))

    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(async () => {
      const { trackError } = await import('../../utils/errorTracker')
      expect(trackError).toHaveBeenCalled()
    })

    expect(await screen.findByTestId('complaints-list-unavailable')).toBeInTheDocument()
    expect(screen.getByText('Complaints unavailable')).toBeInTheDocument()
    expect(screen.queryByText('No complaints found')).not.toBeInTheDocument()
    expect(mockToastError).toHaveBeenCalledWith('Complaints list unavailable: Server unavailable')
  })

  it('shows SMTP honesty banner when email is not configured', async () => {
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: false } })

    render(<Complaints />, { wrapper: Wrapper })

    expect(await screen.findByTestId('complaints-email-unavailable')).toBeInTheDocument()
    expect(screen.getByText('Email alerts unavailable')).toBeInTheDocument()
  })

  it('creates a complaint, toasts, and navigates to detail', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('complaints.new'))

    await waitFor(() => {
      expect(screen.getByTestId('complaints-create-form')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(mockContractsList).toHaveBeenCalled()
    })

    await fillRequiredCreateFields()
    fireEvent.click(screen.getByText('complaints.create'))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledTimes(1)
    })

    const callArgs = mockCreate.mock.calls[0][0]
    expect(callArgs.title).toBe('New complaint')
    expect(callArgs.description).toBe('Detailed description')
    expect(callArgs.contract_id).toBe(10)
    expect(callArgs.source_type).toBe('manual')
    expect(mockToastSuccess).toHaveBeenCalled()
    expect(mockNavigate).toHaveBeenCalledWith('/complaints/3')
  })

  it('shows error when creation fails', async () => {
    mockCreate.mockRejectedValue(new Error('Validation failed'))

    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('complaints.new'))

    await waitFor(() => {
      expect(screen.getByTestId('complaints-create-form')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(mockContractsList).toHaveBeenCalled()
    })

    await fillRequiredCreateFields()
    fireEvent.change(screen.getByPlaceholderText('complaints.form.title_placeholder'), {
      target: { value: 'Bad complaint' },
    })

    fireEvent.click(screen.getByText('complaints.create'))

    await waitFor(() => {
      expect(screen.getByText('Validation failed')).toBeInTheDocument()
    })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('filters complaints via search without crashing on null complainant', async () => {
    mockList.mockResolvedValue({
      data: {
        items: [
          ...sampleComplaints,
          {
            id: 9,
            reference_number: 'CMP-009',
            title: 'Null-safe row',
            description: 'Missing complainant',
            complaint_type: 'other',
            priority: 'low',
            status: 'received',
            received_date: '2026-02-20T10:00:00Z',
            complainant_name: null,
            complainant_email: '',
            complainant_phone: '',
          },
        ],
        total: 3,
        page: 1,
        page_size: 50,
        total_pages: 1,
      },
    })

    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    expect(screen.getByText('Null-safe row')).toBeInTheDocument()

    const searchInput = screen.getByPlaceholderText('complaints.search_placeholder')
    fireEvent.change(searchInput, { target: { value: 'delivery' } })

    expect(screen.getByText('Late delivery issue')).toBeInTheDocument()
    expect(screen.queryByText('Billing overcharge')).not.toBeInTheDocument()
    expect(screen.queryByText('Null-safe row')).not.toBeInTheDocument()
  })

  it('navigates to complaint detail when a row is clicked', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    const titleCell = screen.getByText('Late delivery issue')
    fireEvent.click(titleCell)

    expect(mockNavigate).toHaveBeenCalledWith('/complaints/1')
  })
})
