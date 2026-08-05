import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RequirementLifecycleControls } from '../RequirementLifecycleControls'
import type { ComplianceRequirement } from '../../../api/complianceScheduleClient'

const { mockDeactivate, mockUpdate, mockToastError, mockToastSuccess } = vi.hoisted(() => ({
  mockDeactivate: vi.fn(),
  mockUpdate: vi.fn(),
  mockToastError: vi.fn(),
  mockToastSuccess: vi.fn(),
}))

vi.mock('../../../api/client', () => ({
  complianceScheduleApi: {
    deactivateRequirement: mockDeactivate,
    updateRequirement: mockUpdate,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') =>
    err instanceof Error ? err.message : fallback,
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: {
    success: mockToastSuccess,
    error: mockToastError,
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver
  }
})

function requirement(overrides: Partial<ComplianceRequirement> = {}) {
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
  } as unknown as ComplianceRequirement
}

function renderControls(overrides: Partial<ComplianceRequirement> = {}) {
  const onChanged = vi.fn()
  render(<RequirementLifecycleControls requirement={requirement(overrides)} onChanged={onChanged} />)
  return { onChanged }
}

describe('RequirementLifecycleControls: retiring is confirmed, and reversible', () => {
  it('does not retire on the first click — the destructive call waits for confirmation', async () => {
    const user = userEvent.setup()
    renderControls()

    await user.click(screen.getByTestId('compliance-schedule-deactivate'))

    expect(await screen.findByTestId('compliance-schedule-deactivate-confirm')).toBeInTheDocument()
    expect(mockDeactivate).not.toHaveBeenCalled()
  })

  it('cancelling leaves the obligation exactly as it was', async () => {
    const user = userEvent.setup()
    const { onChanged } = renderControls()

    await user.click(screen.getByTestId('compliance-schedule-deactivate'))
    await screen.findByTestId('compliance-schedule-deactivate-confirm')
    await user.click(screen.getByTestId('compliance-schedule-deactivate-cancel'))

    expect(mockDeactivate).not.toHaveBeenCalled()
    expect(onChanged).not.toHaveBeenCalled()
  })

  it('confirming retires it and asks the page to reload', async () => {
    const user = userEvent.setup()
    mockDeactivate.mockResolvedValue({ data: requirement({ is_active: false }) })
    const { onChanged } = renderControls()

    await user.click(screen.getByTestId('compliance-schedule-deactivate'))
    await screen.findByTestId('compliance-schedule-deactivate-confirm')
    await user.click(screen.getByTestId('compliance-schedule-deactivate-confirm-action'))

    await waitFor(() => expect(mockDeactivate).toHaveBeenCalledWith(7))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('a failed retire reports the reason and does not claim success', async () => {
    const user = userEvent.setup()
    mockDeactivate.mockRejectedValue(new Error('Forbidden'))
    const { onChanged } = renderControls()

    await user.click(screen.getByTestId('compliance-schedule-deactivate'))
    await screen.findByTestId('compliance-schedule-deactivate-confirm')
    await user.click(screen.getByTestId('compliance-schedule-deactivate-confirm-action'))

    await waitFor(() => expect(mockToastError).toHaveBeenCalledWith('Forbidden'))
    expect(mockToastSuccess).not.toHaveBeenCalled()
    expect(onChanged).not.toHaveBeenCalled()
  })

  it('a retired obligation offers a way back, and no way to retire it again', () => {
    renderControls({ is_active: false })

    expect(screen.getByTestId('compliance-schedule-reactivate')).toBeInTheDocument()
    expect(screen.queryByTestId('compliance-schedule-deactivate')).not.toBeInTheDocument()
  })

  it('reactivating flips is_active back rather than activating a fresh duplicate', async () => {
    const user = userEvent.setup()
    mockUpdate.mockResolvedValue({ data: requirement() })
    const { onChanged } = renderControls({ is_active: false })

    await user.click(screen.getByTestId('compliance-schedule-reactivate'))

    await waitFor(() => expect(mockUpdate).toHaveBeenCalledWith(7, { is_active: true }))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('a failed reactivate reports the reason', async () => {
    const user = userEvent.setup()
    mockUpdate.mockRejectedValue(new Error('Conflict'))
    const { onChanged } = renderControls({ is_active: false })

    await user.click(screen.getByTestId('compliance-schedule-reactivate'))

    await waitFor(() => expect(mockToastError).toHaveBeenCalledWith('Conflict'))
    expect(onChanged).not.toHaveBeenCalled()
  })
})
