import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ComplianceScheduleDetail from '../ComplianceScheduleDetail'

const { mockGetRequirement, mockListRecords, mockCurrentUserId } = vi.hoisted(() => ({
  mockGetRequirement: vi.fn(),
  mockListRecords: vi.fn(),
  mockCurrentUserId: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  complianceScheduleApi: {
    getRequirement: mockGetRequirement,
    listRecords: mockListRecords,
    deactivateRequirement: vi.fn(),
    updateRequirement: vi.fn(),
  },
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') =>
    err instanceof Error ? err.message : fallback,
}))

vi.mock('../../utils/auth', () => ({ getCurrentUserId: mockCurrentUserId }))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../compliance/RecordCompletionSheet', () => ({ RecordCompletionSheet: () => null }))
vi.mock('../compliance/RequirementFormDialog', () => ({ RequirementFormDialog: () => null }))

function requirement(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    external_id: 'ext-7',
    tenant_id: 1,
    reference_number: 'CSR-2026-0001',
    title: 'Fire Risk Assessment',
    taxonomy_id: 'CS.01',
    description: null,
    regulatory_basis: null,
    frequency_months: 12,
    frequency_days: null,
    anchor: 'schedule',
    statutory: true,
    next_due_date: '2026-09-06',
    last_completed_at: null,
    owner_id: 1,
    location_id: null,
    is_active: true,
    status: 'current',
    created_at: '2026-08-05T09:00:00Z',
    ...overrides,
  }
}

function renderDetail(overrides: Record<string, unknown> = {}) {
  mockGetRequirement.mockResolvedValue({ data: requirement(overrides) })
  mockListRecords.mockResolvedValue({ data: { items: [] } })
  return render(
    <MemoryRouter initialEntries={['/compliance-schedule/7']}>
      <Routes>
        <Route path="/compliance-schedule/:id" element={<ComplianceScheduleDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockCurrentUserId.mockReturnValue(1)
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver
  }
})

describe('ComplianceScheduleDetail: a retired obligation says it is retired', () => {
  it('explains the retired state instead of leaving a silently inert record', async () => {
    renderDetail({ is_active: false })

    const banner = await screen.findByTestId('compliance-schedule-inactive-banner')
    expect(banner).toHaveTextContent(/no reminders/i)
  })

  it('shows no such banner while the obligation is live', async () => {
    renderDetail()
    await screen.findByTestId('compliance-schedule-detail')

    expect(
      screen.queryByTestId('compliance-schedule-inactive-banner'),
    ).not.toBeInTheDocument()
  })

  it('withholds Edit and Record completion once retired, and offers Reactivate instead', async () => {
    renderDetail({ is_active: false })
    await screen.findByTestId('compliance-schedule-detail')

    expect(screen.queryByTestId('compliance-schedule-open-edit')).not.toBeInTheDocument()
    expect(screen.queryByTestId('compliance-schedule-open-complete')).not.toBeInTheDocument()
    expect(screen.getByTestId('compliance-schedule-reactivate')).toBeInTheDocument()
  })

  it('offers Retire alongside the working controls while live', async () => {
    renderDetail()
    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-open-edit')).toBeInTheDocument(),
    )

    expect(screen.getByTestId('compliance-schedule-deactivate')).toBeInTheDocument()
    expect(screen.queryByTestId('compliance-schedule-reactivate')).not.toBeInTheDocument()
  })
})
