import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ComplianceSchedule from '../ComplianceSchedule'

const { mockListRequirements, mockGetStats, mockListCatalogue, mockActivate } = vi.hoisted(() => ({
  mockListRequirements: vi.fn(),
  mockGetStats: vi.fn(),
  mockListCatalogue: vi.fn(),
  mockActivate: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  complianceScheduleApi: {
    listRequirements: mockListRequirements,
    getStats: mockGetStats,
    listCatalogue: mockListCatalogue,
    activateCatalogue: mockActivate,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') =>
    err instanceof Error ? err.message : fallback,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const STATS = { total_active: 1, current: 1, due_soon: 0, overdue: 0 }

const REQUIREMENT = {
  id: 7,
  title: 'Fire risk assessment',
  reference_number: 'CS-0007',
  next_due_date: '2026-09-01',
  status: 'current',
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ComplianceSchedule />
    </MemoryRouter>,
  )
}

function resolveWith(items: unknown[]) {
  mockListRequirements.mockResolvedValue({ data: { items } })
  mockGetStats.mockResolvedValue({ data: STATS })
  mockListCatalogue.mockResolvedValue({ data: { items: [] } })
}

describe('ComplianceSchedule: an unreadable register is not an empty one', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a persistent failure panel, not the empty state, when the load fails', async () => {
    mockListRequirements.mockRejectedValue(new Error('Network Error'))
    mockGetStats.mockRejectedValue(new Error('Network Error'))
    mockListCatalogue.mockRejectedValue(new Error('Network Error'))

    renderPage()

    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-load-error')).toBeInTheDocument(),
    )

    // The whole point: the page must not claim there is nothing to comply with
    // when it never managed to ask.
    expect(screen.queryByTestId('compliance-schedule-empty')).not.toBeInTheDocument()
    expect(screen.queryByTestId('compliance-schedule-list')).not.toBeInTheDocument()
    expect(screen.getByTestId('compliance-schedule-load-error-retry')).toBeInTheDocument()
    expect(screen.getByTestId('compliance-schedule-load-error')).toHaveTextContent('Network Error')
  })

  it('shows the empty state, and no failure panel, when the load succeeds with nothing', async () => {
    resolveWith([])

    renderPage()

    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-empty')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('compliance-schedule-load-error')).not.toBeInTheDocument()
  })

  it('renders the register when the load succeeds with rows', async () => {
    resolveWith([REQUIREMENT])

    renderPage()

    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-list')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('compliance-schedule-empty')).not.toBeInTheDocument()
    expect(screen.queryByTestId('compliance-schedule-load-error')).not.toBeInTheDocument()
  })

  it('recovers to the register when retry succeeds', async () => {
    mockListRequirements.mockRejectedValueOnce(new Error('Network Error'))
    mockGetStats.mockRejectedValueOnce(new Error('Network Error'))
    mockListCatalogue.mockRejectedValueOnce(new Error('Network Error'))

    renderPage()
    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-load-error')).toBeInTheDocument(),
    )

    resolveWith([REQUIREMENT])
    await userEvent.click(screen.getByTestId('compliance-schedule-load-error-retry'))

    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-list')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('compliance-schedule-load-error')).not.toBeInTheDocument()
  })

  it('does not leave a stale register on screen underneath a failure', async () => {
    resolveWith([REQUIREMENT])
    renderPage()
    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-list')).toBeInTheDocument(),
    )

    // A reload that fails must retract the rows rather than present figures the
    // server has not confirmed.
    mockListRequirements.mockRejectedValue(new Error('Gateway Timeout'))
    mockGetStats.mockRejectedValue(new Error('Gateway Timeout'))
    mockListCatalogue.mockRejectedValue(new Error('Gateway Timeout'))
    await userEvent.click(screen.getByTestId('compliance-schedule-filter-overdue'))

    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-load-error')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('compliance-schedule-list')).not.toBeInTheDocument()
    expect(screen.queryByTestId('compliance-schedule-stats')).not.toBeInTheDocument()
  })
})
