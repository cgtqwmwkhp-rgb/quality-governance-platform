import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Complaints from '../Complaints'

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
  complaintsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
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
    mockCreate.mockResolvedValue({
      data: {
        id: 3,
        reference_number: 'CMP-003',
        title: '',
        description: '',
        complaint_type: 'other',
        priority: 'medium',
        status: 'received',
        received_date: new Date().toISOString(),
        complainant_name: '',
        complainant_email: '',
        complainant_phone: '',
      },
    })
  })

  it('renders loading state initially', () => {
    mockList.mockReturnValue(new Promise(() => {}))
    const { container } = render(<Complaints />, { wrapper: Wrapper })

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
    expect(screen.getByText('complaints.title')).toBeInTheDocument()
  })

  it('renders complaint list after data loads', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    expect(screen.getByText('Late delivery issue')).toBeInTheDocument()
    expect(screen.getByText('CMP-002')).toBeInTheDocument()
    expect(screen.getByText('Billing overcharge')).toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(1, 50)
  })

  it('renders page header and search input', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('complaints.title')).toBeInTheDocument()
    })

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

  it('handles API errors on load and calls trackError', async () => {
    mockList.mockRejectedValue(new Error('Server unavailable'))

    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(async () => {
      const { trackError } = await import('../../utils/errorTracker')
      expect(trackError).toHaveBeenCalled()
    })
  })

  it('creates a complaint via the form', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('complaints.new'))

    await waitFor(() => {
      expect(screen.getByText('complaints.dialog.title')).toBeInTheDocument()
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

    fireEvent.click(screen.getByText('complaints.create'))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledTimes(1)
    })

    const callArgs = mockCreate.mock.calls[0][0]
    expect(callArgs.title).toBe('New complaint')
    expect(callArgs.description).toBe('Detailed description')
  })

  it('shows error when creation fails', async () => {
    mockCreate.mockRejectedValue(new Error('Validation failed'))

    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('complaints.new'))

    await waitFor(() => {
      expect(screen.getByText('complaints.dialog.title')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText('complaints.form.title_placeholder'), {
      target: { value: 'Bad complaint' },
    })
    fireEvent.change(screen.getByPlaceholderText('complaints.form.description_placeholder'), {
      target: { value: 'Some description' },
    })
    fireEvent.change(screen.getByPlaceholderText('complaints.form.name_placeholder'), {
      target: { value: 'Jane Doe' },
    })

    fireEvent.click(screen.getByText('complaints.create'))

    await waitFor(() => {
      expect(screen.getByText('Validation failed')).toBeInTheDocument()
    })
  })

  it('filters complaints via search', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    expect(screen.getByText('Billing overcharge')).toBeInTheDocument()

    const searchInput = screen.getByPlaceholderText('complaints.search_placeholder')
    fireEvent.change(searchInput, { target: { value: 'delivery' } })

    expect(screen.getByText('Late delivery issue')).toBeInTheDocument()
    expect(screen.queryByText('Billing overcharge')).not.toBeInTheDocument()
  })

  it('navigates to complaint detail when a row is clicked', async () => {
    render(<Complaints />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })

    const titleCell = screen.getByText('Late delivery issue')
    fireEvent.click(titleCell.closest('tr')!)

    expect(mockNavigate).toHaveBeenCalledWith('/complaints/1')
  })
})
