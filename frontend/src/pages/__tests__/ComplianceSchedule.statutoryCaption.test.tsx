import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ComplianceSchedule from '../ComplianceSchedule'

const { mockListRequirements, mockGetStats, mockListCatalogue } = vi.hoisted(() => ({
  mockListRequirements: vi.fn(),
  mockGetStats: vi.fn(),
  mockListCatalogue: vi.fn(),
}))

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

vi.mock('../../utils/auth', () => ({ getCurrentUserId: () => 1 }))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../compliance/RequirementFormDialog', () => ({ RequirementFormDialog: () => null }))

beforeEach(() => {
  vi.clearAllMocks()
  mockListRequirements.mockResolvedValue({ data: { items: [], total: 4 } })
  mockGetStats.mockResolvedValue({
    data: { total_active: 4, current: 4, due_soon: 0, overdue: 0 },
  })
  mockListCatalogue.mockResolvedValue({ data: { items: [] } })
})

describe('ComplianceSchedule statutory caption (REG-R3)', () => {
  it('asks the API for statutory=true and captions PEL-HSEQ-5056', async () => {
    render(
      <MemoryRouter
        initialEntries={['/compliance-schedule?register=PEL-HSEQ-5056&statutory=true']}
      >
        <ComplianceSchedule />
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(mockListRequirements).toHaveBeenCalledWith(
        expect.objectContaining({ statutory: true }),
      ),
    )
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent('PEL-HSEQ-5056')
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent(
      'statutory obligations only',
    )
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent('Server total: 4')
  })

  it('withholds the server total when clause is a client-only filter', async () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/compliance-schedule?register=PEL-HSEQ-5056&statutory=true&clause=6.1.3',
        ]}
      >
        <ComplianceSchedule />
      </MemoryRouter>,
    )

    await waitFor(() => expect(mockListRequirements).toHaveBeenCalled())
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent('PEL-HSEQ-5056')
    expect(screen.queryByText(/Server total/)).not.toBeInTheDocument()
  })
})
