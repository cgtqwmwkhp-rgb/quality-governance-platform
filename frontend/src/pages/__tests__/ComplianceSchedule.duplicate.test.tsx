import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ComplianceSchedule from '../ComplianceSchedule'

const { mockListRequirements, mockGetStats, mockListCatalogue, mockActivate, mockToastError } =
  vi.hoisted(() => ({
    mockListRequirements: vi.fn(),
    mockGetStats: vi.fn(),
    mockListCatalogue: vi.fn(),
    mockActivate: vi.fn(),
    mockToastError: vi.fn(),
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
  // Stands in for the real helper's envelope unwrapping, which is covered by its
  // own suite; what matters here is that the page passes the error through to it
  // rather than discarding it.
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') => {
    const message = (err as { response?: { data?: { error?: { message?: string } } } })?.response
      ?.data?.error?.message
    return message ?? fallback
  },
}))

vi.mock('../../utils/auth', () => ({ getCurrentUserId: () => 1 }))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: mockToastError, warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../compliance/RequirementFormDialog', () => ({ RequirementFormDialog: () => null }))

const TEMPLATE = { template_key: 'fra', title: 'Fire Risk Assessment', statutory: true }

beforeEach(() => {
  vi.clearAllMocks()
  mockListRequirements.mockResolvedValue({ data: { items: [] } })
  mockGetStats.mockResolvedValue({ data: { total_active: 0, current: 0, due_soon: 0, overdue: 0 } })
  mockListCatalogue.mockResolvedValue({ data: { items: [TEMPLATE] } })
})

function renderPage() {
  return render(
    <MemoryRouter>
      <ComplianceSchedule />
    </MemoryRouter>,
  )
}

describe('ComplianceSchedule: a refused duplicate says which obligation already covers it', () => {
  it('shows the server’s reason rather than a fixed failure string', async () => {
    const user = userEvent.setup()
    mockActivate.mockRejectedValue({
      response: {
        status: 409,
        data: {
          error: {
            code: 'DUPLICATE_ENTITY',
            message: 'This obligation is already on the register as CSR-2026-0001',
          },
        },
      },
    })
    renderPage()

    await user.click(await screen.findByTestId('compliance-schedule-activate-fra'))

    await waitFor(() =>
      expect(mockToastError).toHaveBeenCalledWith(
        'This obligation is already on the register as CSR-2026-0001',
      ),
    )
  })

  it('still falls back to a readable message when the server explains nothing', async () => {
    const user = userEvent.setup()
    mockActivate.mockRejectedValue(new Error('network down'))
    renderPage()

    await user.click(await screen.findByTestId('compliance-schedule-activate-fra'))

    await waitFor(() =>
      expect(mockToastError).toHaveBeenCalledWith('Could not activate template'),
    )
  })
})
