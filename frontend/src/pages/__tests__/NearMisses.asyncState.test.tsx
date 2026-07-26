/**
 * Near Miss register async states.
 *
 * The register used to render a failure banner directly above "No near misses
 * yet", so a 503 read as a statement that nothing had been reported. These
 * cover the precedence the shared primitive enforces.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import NearMisses from '../NearMisses'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../utils/errorTracker', () => ({ trackError: vi.fn() }))

const mockList = vi.fn()

vi.mock('../../api/client', () => ({
  nearMissesApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn(),
  },
  lookupsApi: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
  contractsApi: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../components/FuzzySearchDropdown', () => ({
  default: () => <input data-testid="fuzzy-customer" />,
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

const NEAR_MISS = {
  id: 1,
  reference_number: 'NM-2026-0001',
  contract: 'UK Power Networks',
  location: 'Depot yard',
  event_date: '2026-03-01T09:00:00Z',
  potential_severity: 'high',
  is_hipo: false,
  status: 'open',
}

describe('NearMisses async states', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: { items: [NEAR_MISS], total: 1, page: 1, page_size: 50 } })
  })

  it('shows the failure with a retry control instead of an empty register', async () => {
    mockList.mockRejectedValue(new Error('503 Service Unavailable'))

    render(<NearMisses />, { wrapper: Wrapper })

    const failure = await screen.findByTestId('near-misses-async-error')
    expect(failure).toHaveTextContent('Near misses unavailable')
    expect(failure).toHaveTextContent('503 Service Unavailable')
    expect(screen.queryByText('near_misses.empty.title')).not.toBeInTheDocument()
    expect(screen.getByTestId('near-misses-async-error-retry')).toBeInTheDocument()
  })

  it('retries the load and clears the failure once it succeeds', async () => {
    mockList.mockRejectedValueOnce(new Error('503 Service Unavailable'))

    render(<NearMisses />, { wrapper: Wrapper })

    fireEvent.click(await screen.findByTestId('near-misses-async-error-retry'))

    await waitFor(() => {
      expect(screen.getByText('NM-2026-0001')).toBeInTheDocument()
    })
    // The stale failure must not survive a successful reload.
    expect(screen.queryByTestId('near-misses-async-error')).not.toBeInTheDocument()
  })

  it('still shows the empty state when the register genuinely holds nothing', async () => {
    mockList.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 50 } })

    render(<NearMisses />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('near_misses.empty.title')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('near-misses-async-error')).not.toBeInTheDocument()
  })
})
