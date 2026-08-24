import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FraOcrReviewSheet } from '../FraOcrReviewSheet'
import type { FraOcrDraftResponse } from '../../../api/complianceScheduleFraOcrClient'

const { mockConfirm, mockDiscard, mockToast } = vi.hoisted(() => ({
  mockConfirm: vi.fn(),
  mockDiscard: vi.fn(),
  mockToast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: string | { defaultValue?: string }) => {
      if (typeof opts === 'string') return opts
      if (opts?.defaultValue) return opts.defaultValue
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../contexts/ToastContext', () => ({ toast: mockToast }))

vi.mock('../../../api/client', () => ({
  complianceScheduleFraOcrApi: {
    confirmDraft: mockConfirm,
    discardDraft: mockDiscard,
  },
  getApiErrorMessage: (_e: unknown, fallback?: string) => fallback ?? 'failed',
}))

function emptyField(value: string | null = null, confidence: 'high' | 'medium' | 'none' = 'medium') {
  return { value, confidence, evidence_snippet: value ? `…${value}…` : null }
}

function makeDraft(overrides: Partial<FraOcrDraftResponse> = {}): FraOcrDraftResponse {
  return {
    id: 44,
    external_id: 'ext-44',
    tenant_id: 1,
    requirement_id: 7,
    purpose: 'fra_pas79',
    status: 'pending',
    source_filename: 'fra-sample.pdf',
    source_checksum_sha256: 'abc',
    proposed: {
      assessment_date: emptyField('2026-03-01', 'high'),
      next_review_date: emptyField('2027-03-01', 'high'),
      review_interval_months: emptyField('12'),
      assessor_name: emptyField('A. Assessor'),
      assessor_organisation: emptyField('Acme Fire'),
      premises_name: emptyField('Depot A'),
      pas79_reference: emptyField('PAS 79-1:2020'),
      overall_risk_rating: emptyField('Tolerable'),
    },
    proposed_actions: [
      {
        index: 0,
        source_ref: 'PA1',
        text: 'Replace extinguisher',
        priority_normalised: 'high',
        target_date: '2026-09-01',
        confidence: 'high',
        needs_review: false,
      },
      {
        index: 1,
        source_ref: 'PA2',
        text: 'Clarify compartmentation',
        priority_normalised: null,
        target_date: null,
        confidence: 'none',
        needs_review: true,
      },
    ],
    warnings: ['Low OCR confidence on page 3'],
    filing_status: 'not_filed',
    created_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

function renderSheet(
  overrides: Partial<{
    open: boolean
    draft: FraOcrDraftResponse | null
    onConfirmed: (r: unknown) => void
    onOpenChange: (open: boolean) => void
  }> = {},
) {
  const onConfirmed = overrides.onConfirmed ?? vi.fn()
  const onOpenChange = overrides.onOpenChange ?? vi.fn()
  render(
    <FraOcrReviewSheet
      open={overrides.open ?? true}
      onOpenChange={onOpenChange}
      draft={overrides.draft ?? makeDraft()}
      onConfirmed={onConfirmed as never}
    />,
  )
  return { onConfirmed, onOpenChange }
}

describe('FraOcrReviewSheet human gate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockConfirm.mockResolvedValue({
      data: {
        draft: { ...makeDraft(), status: 'confirmed' },
        requirement: { id: 7, next_due_date: '2027-03-01' },
        applied: {},
      },
    })
  })

  it('keeps Confirm disabled until the due date field is focused and blurred', async () => {
    const user = userEvent.setup()
    renderSheet()

    const confirm = screen.getByTestId('fra-ocr-confirm')
    expect(confirm).toBeDisabled()

    const due = screen.getByTestId('fra-ocr-next-due-date')
    expect(due).toHaveValue('2027-03-01')

    await user.click(due)
    await user.tab()

    await waitFor(() => expect(confirm).not.toBeDisabled())
  })

  it('sends next_due_date in the confirm payload after the gate is satisfied', async () => {
    const user = userEvent.setup()
    const { onConfirmed } = renderSheet()

    const due = screen.getByTestId('fra-ocr-next-due-date')
    await user.clear(due)
    await user.type(due, '2027-06-15')
    await user.tab()

    await user.click(screen.getByTestId('fra-ocr-confirm'))

    await waitFor(() => expect(mockConfirm).toHaveBeenCalled())
    expect(mockConfirm).toHaveBeenCalledWith(
      44,
      expect.objectContaining({
        next_due_date: '2027-06-15',
        acknowledged_warnings: true,
        actions: [
          expect.objectContaining({
            index: 0,
            text: 'Replace extinguisher',
            priority_normalised: 'high',
            target_date: '2026-09-01',
          }),
        ],
      }),
    )
    expect(onConfirmed).toHaveBeenCalled()
    expect(mockToast.success).toHaveBeenCalled()
  })

  it('leaves needs_review actions unchecked by default', () => {
    renderSheet()
    expect(screen.getByTestId('fra-ocr-action-check-0')).toBeChecked()
    expect(screen.getByTestId('fra-ocr-action-check-1')).not.toBeChecked()
  })
})
