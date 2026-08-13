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
    getLocationCoverageGaps: vi.fn().mockResolvedValue({
      data: { total_locations: 0, missing_fra: 0, missing_fire_drill: 0, missing_both: 0, items: [] },
    }),
    importDryRun: vi.fn(),
    importCommit: vi.fn(),
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

const STATS = { total_active: 2, current: 2, due_soon: 0, overdue: 0 }

function requirement(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    title: 'Fire risk assessment',
    reference_number: 'CS-0007',
    next_due_date: '2026-09-01',
    status: 'current',
    owner_id: 1,
    is_active: true,
    ...overrides,
  }
}

function resolveWith(items: unknown[]) {
  mockListRequirements.mockResolvedValue({ data: { items } })
  mockGetStats.mockResolvedValue({ data: STATS })
  mockListCatalogue.mockResolvedValue({ data: { items: [] } })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockCurrentUserId.mockReturnValue(1)
})

describe('ComplianceSchedule programme deep-link (SG-D-02)', () => {
  it('filters to obligations that mention the clause and keeps Schedule as SoR', async () => {
    resolveWith([
      requirement({ id: 7, title: 'Fire risk assessment' }),
      requirement({
        id: 8,
        title: 'Legal register (ISO 9001 6.1.3)',
        reference_number: 'CS-0008',
      }),
    ])

    render(
      <MemoryRouter initialEntries={['/compliance-schedule?clause=6.1.3&framework=9001']}>
        <ComplianceSchedule />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByTestId('compliance-schedule-list')).toBeInTheDocument())
    expect(screen.getByTestId('compliance-schedule-programme-context')).toBeInTheDocument()
    expect(screen.getByTestId('compliance-schedule-row-8')).toBeInTheDocument()
    expect(screen.queryByTestId('compliance-schedule-row-7')).not.toBeInTheDocument()
  })

  it('does not empty the register when no obligation cites the clause', async () => {
    resolveWith([requirement()])

    render(
      <MemoryRouter initialEntries={['/compliance-schedule?clause=6.1.3&framework=9001']}>
        <ComplianceSchedule />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByTestId('compliance-schedule-row-7')).toBeInTheDocument())
    expect(screen.getByTestId('compliance-schedule-programme-context')).toHaveTextContent(
      /full register shown/i,
    )
  })

  it('clears clause context and shows the full register again', async () => {
    resolveWith([
      requirement({ id: 7, title: 'Fire risk assessment' }),
      requirement({
        id: 8,
        title: 'Legal register (ISO 9001 6.1.3)',
        reference_number: 'CS-0008',
      }),
    ])

    render(
      <MemoryRouter initialEntries={['/compliance-schedule?clause=6.1.3&framework=9001']}>
        <ComplianceSchedule />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByTestId('compliance-schedule-row-8')).toBeInTheDocument())
    await userEvent.click(screen.getByTestId('compliance-schedule-clear-programme-context'))
    await waitFor(() => expect(screen.getByTestId('compliance-schedule-row-7')).toBeInTheDocument())
    expect(screen.queryByTestId('compliance-schedule-programme-context')).not.toBeInTheDocument()
  })
})
