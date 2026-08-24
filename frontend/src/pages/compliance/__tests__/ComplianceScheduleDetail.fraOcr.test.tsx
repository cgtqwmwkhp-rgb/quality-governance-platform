import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ComplianceScheduleDetail from '../../ComplianceScheduleDetail'

const {
  mockGetRequirement,
  mockListRecords,
  mockCurrentUserId,
  mockUseFeatureFlag,
  mockListDrafts,
} = vi.hoisted(() => ({
  mockGetRequirement: vi.fn(),
  mockListRecords: vi.fn(),
  mockCurrentUserId: vi.fn(),
  mockUseFeatureFlag: vi.fn(),
  mockListDrafts: vi.fn(),
}))

vi.mock('../../../api/client', () => ({
  complianceScheduleApi: {
    getRequirement: mockGetRequirement,
    listRecords: mockListRecords,
  },
  complianceScheduleFraOcrApi: {
    listDrafts: mockListDrafts,
  },
  getApiErrorMessage: () => 'failed',
}))

vi.mock('../../../utils/auth', () => ({
  getCurrentUserId: mockCurrentUserId,
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: mockUseFeatureFlag,
}))

vi.mock('../RecordCompletionSheet', () => ({
  RecordCompletionSheet: () => null,
}))

vi.mock('../RequirementFormDialog', () => ({
  RequirementFormDialog: () => null,
}))

function requirement(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    external_id: 'ext-7',
    tenant_id: 1,
    reference_number: 'CSR-2026-0001',
    title: 'Fire Risk Assessment',
    taxonomy_id: '03.01',
    description: null,
    regulatory_basis: 'Regulatory Reform (Fire Safety) Order 2005',
    frequency_months: 12,
    frequency_days: null,
    anchor: 'schedule',
    statutory: true,
    next_due_date: '2026-09-06',
    last_completed_at: null,
    owner_id: null,
    location_id: 42,
    is_active: true,
    status: 'current',
    created_at: '2026-08-05T09:00:00Z',
    fra_ocr_eligible: true,
    ...overrides,
  }
}

function renderDetail() {
  mockGetRequirement.mockResolvedValue({ data: requirement() })
  mockListRecords.mockResolvedValue({ data: { items: [] } })
  mockListDrafts.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 50, pages: 0 } })
  return render(
    <MemoryRouter initialEntries={['/compliance-schedule/7']}>
      <Routes>
        <Route path="/compliance-schedule/:id" element={<ComplianceScheduleDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ComplianceScheduleDetail FRA OCR panel visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCurrentUserId.mockReturnValue(1)
  })

  it('hides the FRA OCR panel when the feature flag is off', async () => {
    mockUseFeatureFlag.mockReturnValue(false)
    renderDetail()

    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-detail')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('fra-ocr-panel')).not.toBeInTheDocument()
    expect(mockListDrafts).not.toHaveBeenCalled()
  })

  it('shows the FRA OCR panel when the flag is on and the obligation is eligible', async () => {
    mockUseFeatureFlag.mockImplementation((flag: string) => flag === 'compliance_schedule_fra_ocr')
    renderDetail()

    await waitFor(() => expect(screen.getByTestId('fra-ocr-panel')).toBeInTheDocument())
    expect(mockListDrafts).toHaveBeenCalledWith(7, { page_size: 50 })
  })
})
