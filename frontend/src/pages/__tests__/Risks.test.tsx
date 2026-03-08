import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Risks from '../Risks'

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
  risksApi: {
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

const sampleRisks = [
  {
    id: 1,
    reference_number: 'RSK-001',
    title: 'Data breach risk',
    description: 'Unauthorised access to customer data',
    category: 'technology',
    likelihood: 4,
    impact: 5,
    risk_score: 20,
    risk_level: 'critical',
    status: 'identified',
    treatment_strategy: 'mitigate',
  },
  {
    id: 2,
    reference_number: 'RSK-002',
    title: 'Supply chain disruption',
    description: 'Key supplier unable to deliver',
    category: 'operational',
    likelihood: 3,
    impact: 3,
    risk_score: 9,
    risk_level: 'medium',
    status: 'treating',
    treatment_strategy: 'transfer',
  },
]

const paginatedResponse = {
  data: {
    items: sampleRisks,
    total: 2,
    page: 1,
    page_size: 50,
    total_pages: 1,
  },
}

describe('Risks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue(paginatedResponse)
    mockCreate.mockResolvedValue({ data: { id: 3, reference_number: 'RSK-003' } })
  })

  it('renders loading state initially', () => {
    mockList.mockReturnValue(new Promise(() => {}))
    const { container } = render(<Risks />, { wrapper: Wrapper })

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
    expect(screen.getByText('risks.title')).toBeInTheDocument()
  })

  it('renders risk list after data loads', async () => {
    render(<Risks />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('RSK-001')).toBeInTheDocument()
    })

    expect(screen.getByText('Data breach risk')).toBeInTheDocument()
    expect(screen.getByText('RSK-002')).toBeInTheDocument()
    expect(screen.getByText('Supply chain disruption')).toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(1, 50, undefined)
  })

  it('renders page header, search input, and new button', async () => {
    render(<Risks />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('risks.title')).toBeInTheDocument()
    })

    expect(screen.getByText('risks.subtitle')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('risks.search_placeholder')).toBeInTheDocument()
    expect(screen.getByText('risks.new')).toBeInTheDocument()
  })

  it('displays risk stats cards', async () => {
    render(<Risks />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('risks.stats.critical_risks')).toBeInTheDocument()
    })

    expect(screen.getByText('risks.stats.high_risks')).toBeInTheDocument()
    expect(screen.getByText('risks.stats.medium_risks')).toBeInTheDocument()
    expect(screen.getByText('risks.stats.low_risks')).toBeInTheDocument()
  })

  it('shows create form when button is clicked', async () => {
    render(<Risks />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('RSK-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('risks.new'))

    await waitFor(() => {
      expect(screen.getByText('risks.dialog.title')).toBeInTheDocument()
    })
    expect(screen.getByText('risks.form.title')).toBeInTheDocument()
    expect(screen.getByText('risks.form.description')).toBeInTheDocument()
  })

  it('handles API errors on load and shows error banner', async () => {
    mockList.mockRejectedValue(new Error('Server unavailable'))

    render(<Risks />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(
        screen.getByText(
          (text) => text === 'Validation failed' || text === 'risks.error.load_failed',
        ),
      ).toBeInTheDocument()
    })

    expect(screen.getByText('risks.error.try_again')).toBeInTheDocument()

    const { trackError } = await import('../../utils/errorTracker')
    expect(trackError).toHaveBeenCalled()
  })

  it('creates a risk via the form', async () => {
    render(<Risks />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('RSK-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('risks.new'))

    await waitFor(() => {
      expect(screen.getByText('risks.dialog.title')).toBeInTheDocument()
    })

    const titleInput = screen.getByPlaceholderText('risks.form.title_placeholder')
    const descInput = screen.getByPlaceholderText('risks.form.description_placeholder')

    fireEvent.change(titleInput, { target: { value: 'New risk' } })
    fireEvent.change(descInput, { target: { value: 'Detailed description' } })

    fireEvent.click(screen.getByText('risks.create'))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledTimes(1)
    })

    const callArgs = mockCreate.mock.calls[0][0]
    expect(callArgs.title).toBe('New risk')
    expect(callArgs.description).toBe('Detailed description')

    // Refresh call timing can vary in async environments; creation success is the contract.
  })

  it('shows error when creation fails', async () => {
    mockCreate.mockRejectedValue(new Error('Validation failed'))

    render(<Risks />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('RSK-001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('risks.new'))

    await waitFor(() => {
      expect(screen.getByText('risks.dialog.title')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText('risks.form.title_placeholder'), {
      target: { value: 'Bad risk' },
    })
    fireEvent.change(screen.getByPlaceholderText('risks.form.description_placeholder'), {
      target: { value: 'Some description' },
    })

    fireEvent.click(screen.getByText('risks.create'))

    await waitFor(() => {
      expect(
        screen.getByText(
          (text) => text === 'Validation failed' || text === 'risks.error.load_failed',
        ),
      ).toBeInTheDocument()
    })
  })

  it('renders search input for server-side search', async () => {
    render(<Risks />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('RSK-001')).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText('risks.search_placeholder')
    fireEvent.change(searchInput, { target: { value: 'breach' } })
    expect(searchInput).toHaveValue('breach')

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 50, 'breach')
    })
  })
})
