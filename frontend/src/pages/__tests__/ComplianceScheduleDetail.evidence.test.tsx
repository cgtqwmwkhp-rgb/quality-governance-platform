import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ComplianceScheduleDetail from '../ComplianceScheduleDetail'

const { mockGetRequirement, mockListRecords, mockEvidenceList, mockCurrentUserId } = vi.hoisted(
  () => ({
    mockGetRequirement: vi.fn(),
    mockListRecords: vi.fn(),
    mockEvidenceList: vi.fn(),
    mockCurrentUserId: vi.fn(),
  }),
)

vi.mock('../../api/client', () => ({
  complianceScheduleApi: {
    getRequirement: mockGetRequirement,
    listRecords: mockListRecords,
  },
  evidenceAssetsApi: {
    list: mockEvidenceList,
    upload: vi.fn(),
    delete: vi.fn(),
    getSignedUrl: vi.fn(),
  },
  getApiErrorMessage: (_err: unknown, fallback: string) => fallback,
}))

vi.mock('../../utils/auth', () => ({
  getCurrentUserId: mockCurrentUserId,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../compliance/RecordCompletionSheet', () => ({
  RecordCompletionSheet: () => null,
}))

vi.mock('../compliance/RequirementFormDialog', () => ({
  RequirementFormDialog: () => null,
}))

vi.mock('../compliance/RequirementLifecycleControls', () => ({
  RequirementLifecycleControls: () => null,
}))

function requirement(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    external_id: 'ext-7',
    tenant_id: 1,
    reference_number: 'CSR-2026-0001',
    title: 'Fire Risk Assessment',
    taxonomy_id: 'CS.01',
    description: null,
    regulatory_basis: 'RRO 2005',
    frequency_months: 12,
    frequency_days: null,
    anchor: 'schedule',
    statutory: true,
    next_due_date: '2026-09-06',
    last_completed_at: '2026-08-01T10:00:00Z',
    owner_id: 1,
    location_id: null,
    is_active: true,
    status: 'current',
    created_at: '2026-08-05T09:00:00Z',
    ...overrides,
  }
}

function record(overrides: Record<string, unknown> = {}) {
  return {
    id: 41,
    external_id: 'rec-41',
    tenant_id: 1,
    requirement_id: 7,
    reference_number: 'CRC-2026-0041',
    due_date: '2026-08-01',
    completed_at: '2026-08-01T10:00:00Z',
    outcome: 'completed',
    check_passed: true,
    notes: null,
    evidence_asset_ids: [],
    created_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

function renderDetail(records: Record<string, unknown>[] = []) {
  mockGetRequirement.mockResolvedValue({ data: requirement() })
  mockListRecords.mockResolvedValue({ data: { items: records } })
  mockEvidenceList.mockResolvedValue({ data: { items: [] } })
  return render(
    <MemoryRouter initialEntries={['/compliance-schedule/7']}>
      <Routes>
        <Route path="/compliance-schedule/:id" element={<ComplianceScheduleDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ComplianceScheduleDetail: evidence attaches to an occurrence, not the obligation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCurrentUserId.mockReturnValue(1)
  })

  it('explains why there is no evidence panel when nothing has been completed yet', async () => {
    renderDetail([])
    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-evidence-needs-record')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('compliance-schedule-record-evidence-41')).not.toBeInTheDocument()
    expect(mockEvidenceList).not.toHaveBeenCalled()
  })

  it('does not fetch evidence until the occurrence is opened', async () => {
    const user = userEvent.setup()
    renderDetail([record()])
    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-record-evidence-41')).toBeInTheDocument(),
    )
    expect(mockEvidenceList).not.toHaveBeenCalled()

    await user.click(screen.getByTestId('compliance-schedule-record-evidence-toggle-41'))

    await waitFor(() => expect(mockEvidenceList).toHaveBeenCalled())
    expect(mockEvidenceList).toHaveBeenCalledWith(
      expect.objectContaining({
        source_module: 'compliance_record',
        source_id: 41,
      }),
    )
    expect(screen.getByTestId('compliance-record-41-evidence-panel')).toBeInTheDocument()
  })

  it('keeps each occurrence on its own evidence list', async () => {
    const user = userEvent.setup()
    renderDetail([record({ id: 41 }), record({ id: 42, reference_number: 'CRC-2026-0042' })])
    await waitFor(() =>
      expect(screen.getByTestId('compliance-schedule-record-evidence-42')).toBeInTheDocument(),
    )

    await user.click(screen.getByTestId('compliance-schedule-record-evidence-toggle-42'))

    await waitFor(() =>
      expect(mockEvidenceList).toHaveBeenCalledWith(
        expect.objectContaining({ source_module: 'compliance_record', source_id: 42 }),
      ),
    )
    expect(mockEvidenceList).not.toHaveBeenCalledWith(expect.objectContaining({ source_id: 41 }))
  })
})
