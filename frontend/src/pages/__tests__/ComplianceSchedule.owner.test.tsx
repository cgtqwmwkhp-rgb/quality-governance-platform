import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ComplianceSchedule from '../ComplianceSchedule'

const { mockListRequirements, mockGetStats, mockListCatalogue, mockActivate, mockCurrentUserId } =
  vi.hoisted(() => ({
    mockListRequirements: vi.fn(),
    mockGetStats: vi.fn(),
    mockListCatalogue: vi.fn(),
    mockActivate: vi.fn(),
    mockCurrentUserId: vi.fn(),
  }))

vi.mock('../../api/client', () => ({
  complianceScheduleApi: {
    listRequirements: mockListRequirements,
    getStats: mockGetStats,
    getLocationCoverageGaps: vi.fn().mockResolvedValue({ data: { total_locations: 0, missing_fra: 0, missing_fire_drill: 0, missing_both: 0, items: [] } }),
    importDryRun: vi.fn(),
    importCommit: vi.fn(),
    listCatalogue: mockListCatalogue,
    activateCatalogue: mockActivate,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') =>
    err instanceof Error ? err.message : fallback,
}))

vi.mock('../../utils/auth', () => ({
  getCurrentUserId: mockCurrentUserId,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const STATS = { total_active: 1, current: 1, due_soon: 0, overdue: 0 }

const TEMPLATE = { template_key: 'fire_risk_assessment', title: 'Fire Risk Assessment', statutory: true }

function requirement(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    title: 'Fire risk assessment',
    reference_number: 'CS-0007',
    next_due_date: '2026-09-01',
    status: 'current',
    owner_id: null,
    ...overrides,
  }
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ComplianceSchedule />
    </MemoryRouter>,
  )
}

function resolveWith(items: unknown[], templates: unknown[] = [TEMPLATE]) {
  mockListRequirements.mockResolvedValue({ data: { items } })
  mockGetStats.mockResolvedValue({ data: STATS })
  mockListCatalogue.mockResolvedValue({ data: { items: templates } })
  mockActivate.mockResolvedValue({ data: requirement() })
}

describe('ComplianceSchedule: an activated obligation always has someone to notify', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCurrentUserId.mockReturnValue(42)
  })

  it('assigns the activating user as owner', async () => {
    resolveWith([])
    renderPage()
    await waitFor(() => expect(mockListCatalogue).toHaveBeenCalled())

    await userEvent.click(
      screen.getByTestId('compliance-schedule-activate-fire_risk_assessment'),
    )

    await waitFor(() => expect(mockActivate).toHaveBeenCalled())
    const [key, payload] = mockActivate.mock.calls[0]
    expect(key).toBe('fire_risk_assessment')
    // Without this the obligation is unowned, and reminders fall back to the
    // admin role -- which nobody holds in some estates, so nobody is told.
    expect(payload.owner_id).toBe(42)
    expect(payload.next_due_date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('omits the owner rather than sending a bogus one when the user is unidentifiable', async () => {
    mockCurrentUserId.mockReturnValue(null)
    resolveWith([])
    renderPage()
    await waitFor(() => expect(mockListCatalogue).toHaveBeenCalled())

    await userEvent.click(
      screen.getByTestId('compliance-schedule-activate-fire_risk_assessment'),
    )

    await waitFor(() => expect(mockActivate).toHaveBeenCalled())
    const [, payload] = mockActivate.mock.calls[0]
    expect(payload.owner_id).toBeUndefined()
    expect(payload).not.toHaveProperty('owner_id', null)
  })

  it('shows on the row who owns each obligation', async () => {
    resolveWith([
      requirement({ id: 1, owner_id: 42 }),
      requirement({ id: 2, owner_id: 99 }),
      requirement({ id: 3, owner_id: null }),
    ])
    renderPage()

    await waitFor(() => expect(screen.getByTestId('compliance-schedule-list')).toBeInTheDocument())

    expect(screen.getByTestId('compliance-schedule-owner-1')).toHaveTextContent('Owned by you')
    expect(screen.getByTestId('compliance-schedule-owner-2')).toHaveTextContent(
      'Owned by someone else',
    )
    // The case that matters operationally: an unowned obligation is visibly
    // unowned, not silently blank.
    expect(screen.getByTestId('compliance-schedule-owner-3')).toHaveTextContent('Unassigned')
  })
})
