import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ComplianceSchedule from '../ComplianceSchedule'

const { mockListRequirements, mockGetStats, mockListCatalogue, mockCurrentUserId } = vi.hoisted(
  () => ({
    mockListRequirements: vi.fn(),
    mockGetStats: vi.fn(),
    mockListCatalogue: vi.fn(),
    mockCurrentUserId: vi.fn(),
  }),
)

vi.mock('../../api/client', () => ({
  complianceScheduleApi: {
    listRequirements: mockListRequirements,
    getStats: mockGetStats,
    getLocationCoverageGaps: vi.fn().mockResolvedValue({ data: { total_locations: 0, missing_fra: 0, missing_fire_drill: 0, missing_both: 0, items: [] } }),
    listCatalogue: mockListCatalogue,
    activateCatalogue: vi.fn(),
  },
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') =>
    err instanceof Error ? err.message : fallback,
}))

vi.mock('../../utils/auth', () => ({ getCurrentUserId: mockCurrentUserId }))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../compliance/RequirementFormDialog', () => ({ RequirementFormDialog: () => null }))

const STATS = { total_active: 1, current: 1, due_soon: 0, overdue: 0 }
const TEMPLATE = { template_key: 'fra', title: 'Fire Risk Assessment', statutory: true }

function requirement(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    title: 'Fire risk assessment',
    reference_number: 'CS-0007',
    next_due_date: '2026-01-01',
    status: 'overdue',
    owner_id: 1,
    is_active: true,
    ...overrides,
  }
}

function resolveWith(items: unknown[]) {
  mockListRequirements.mockResolvedValue({ data: { items } })
  mockGetStats.mockResolvedValue({ data: STATS })
  mockListCatalogue.mockResolvedValue({ data: { items: [TEMPLATE] } })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ComplianceSchedule />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockCurrentUserId.mockReturnValue(1)
})

describe('ComplianceSchedule: the retired view is a separate register, not a filter', () => {
  it('asks the API for active obligations until the user says otherwise', async () => {
    resolveWith([requirement()])
    renderPage()

    await waitFor(() =>
      expect(mockListRequirements).toHaveBeenCalledWith(
        expect.objectContaining({ is_active: true }),
      ),
    )
  })

  it('switching to Retired re-queries for inactive rows', async () => {
    const user = userEvent.setup()
    resolveWith([requirement()])
    renderPage()
    await screen.findByTestId('compliance-schedule-list')

    await user.click(screen.getByTestId('compliance-schedule-toggle-inactive'))

    await waitFor(() =>
      expect(mockListRequirements).toHaveBeenCalledWith(
        expect.objectContaining({ is_active: false }),
      ),
    )
  })

  it('labels a retired row Retired rather than repeating a due status it is no longer held to', async () => {
    const user = userEvent.setup()
    resolveWith([requirement({ is_active: false })])
    renderPage()
    await screen.findByTestId('compliance-schedule-list')

    await user.click(screen.getByTestId('compliance-schedule-toggle-inactive'))

    expect(await screen.findByTestId('compliance-schedule-retired-7')).toBeInTheDocument()
    // Scoped to the list: "Overdue" is also one of the status filter buttons in
    // the header, which stays available in this view.
    expect(screen.getByTestId('compliance-schedule-list')).not.toHaveTextContent('Overdue')
  })

  it('hides the counters and the catalogue, which both describe the active register', async () => {
    const user = userEvent.setup()
    resolveWith([requirement({ is_active: false })])
    renderPage()
    await screen.findByTestId('compliance-schedule-stats')

    await user.click(screen.getByTestId('compliance-schedule-toggle-inactive'))

    await waitFor(() =>
      expect(screen.queryByTestId('compliance-schedule-stats')).not.toBeInTheDocument(),
    )
    expect(screen.queryByTestId('compliance-schedule-catalogue')).not.toBeInTheDocument()
    expect(screen.queryByTestId('compliance-schedule-add')).not.toBeInTheDocument()
  })

  it('an empty retired list says so, rather than pointing at the catalogue', async () => {
    const user = userEvent.setup()
    resolveWith([])
    renderPage()
    await screen.findByTestId('compliance-schedule-empty')

    await user.click(screen.getByTestId('compliance-schedule-toggle-inactive'))

    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-empty')).toHaveTextContent(
        /nothing has been retired/i,
      ),
    )
  })

  it('the toggle reports its own state to assistive technology', async () => {
    const user = userEvent.setup()
    resolveWith([])
    renderPage()
    const toggle = await screen.findByTestId('compliance-schedule-toggle-inactive')

    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
  })
})
