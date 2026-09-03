/**
 * AUD-F3: one rejected question must not take the rest of the audit with it.
 *
 * AUD-2026-0087 was saved by a single sequential loop that threw out of itself
 * on the first rejected question, so question 1's 400 meant questions 2..14
 * were never attempted at all — and a later, partially-successful pass still
 * cleared the dirty flag and deleted the local draft, which is how a run ended
 * up with photos in Azure and zero answer rows.
 *
 * These render the real page rather than a extracted helper on purpose: the
 * defect was in how the page decided the server was the source of truth, not in
 * any single request.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AuditExecution from '../AuditExecution'
import { deleteAuditDraft } from '../../services/auditDraftStore'

const mockNavigate = vi.fn()
const mockGetRunDetail = vi.fn()
const mockGetTemplate = vi.fn()
const mockUpsertByQuestion = vi.fn()
const mockCreateResponse = vi.fn()
const mockUpdateResponse = vi.fn()
const mockCompleteRun = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api/client', () => ({
  auditsApi: {
    getRunDetail: (...args: unknown[]) => mockGetRunDetail(...args),
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    upsertByQuestion: (...args: unknown[]) => mockUpsertByQuestion(...args),
    createResponse: (...args: unknown[]) => mockCreateResponse(...args),
    updateResponse: (...args: unknown[]) => mockUpdateResponse(...args),
    startRun: vi.fn().mockResolvedValue({ data: {} }),
    acknowledgeRun: vi.fn().mockResolvedValue({ data: {} }),
    completeRun: (...args: unknown[]) => mockCompleteRun(...args),
    uploadQuestionEvidence: vi
      .fn()
      .mockResolvedValue({ data: { evidence_asset_id: 99, response_id: 7, evidence_asset_ids: [99] } }),
  },
  evidenceAssetsApi: {
    upload: vi.fn().mockResolvedValue({ data: { id: 99 } }),
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    getSignedUrl: vi.fn().mockResolvedValue({ data: { signed_url: 'https://example.com/photo.jpg' } }),
    getContent: vi.fn().mockResolvedValue({ data: new Blob(['photo-bytes']) }),
    delete: vi.fn().mockResolvedValue({}),
  },
  getApiErrorMessage: (error: unknown, fallback?: string) =>
    error instanceof Error ? error.message : (fallback ?? 'Request failed'),
}))

vi.mock('../../services/auditDraftStore', () => ({
  registerDraftSnapshot: vi.fn(),
  getAuditDraft: vi.fn().mockResolvedValue(null),
  deleteAuditDraft: vi.fn(),
  saveAuditDraft: vi.fn().mockResolvedValue({ ok: true }),
  putCaptureBlob: vi.fn().mockResolvedValue({ ok: true }),
  deleteCaptureBlob: vi.fn().mockResolvedValue(undefined),
  listCaptureBlobs: vi.fn().mockResolvedValue([]),
  ensureDeviceLedgerDurability: vi.fn().mockResolvedValue({
    durable: true,
    reason: 'ok',
    message: '',
    writeFailed: false,
    usageBytes: null,
    quotaBytes: null,
  }),
  subscribeDeviceLedgerStatus: vi.fn(() => () => {}),
  getDeviceLedgerStatus: vi.fn(() => ({
    durable: true,
    reason: 'ok',
    message: '',
    writeFailed: false,
    usageBytes: null,
    quotaBytes: null,
  })),
}))

const FIRST_QUESTION_ID = 151
const SECOND_QUESTION_ID = 152
const RUN_ID = 42

function renderPage() {
  render(
    <MemoryRouter initialEntries={[`/audits/${RUN_ID}/execute`]}>
      <Routes>
        <Route path="/audits/:auditId/execute" element={<AuditExecution />} />
      </Routes>
    </MemoryRouter>,
  )
}

function mockExecutableAudit() {
  mockGetRunDetail.mockResolvedValue({
    data: {
      id: RUN_ID,
      reference_number: 'AUD-2026-0087',
      template_id: 12,
      template_version: 1,
      title: 'Field Technician Audit',
      location: 'ME14 3DA',
      status: 'in_progress',
      responses: [],
      findings: [],
      completion_percentage: 0,
      created_at: '2026-09-02T11:15:00Z',
    },
  })
  mockGetTemplate.mockResolvedValue({
    data: {
      id: 12,
      name: 'Field Technician Audit',
      audit_type: 'internal',
      version: 1,
      scoring_method: 'percentage',
      allow_offline: false,
      require_gps: false,
      require_signature: false,
      require_approval: false,
      auto_create_findings: true,
      is_active: true,
      is_published: true,
      sections: [
        {
          id: 6,
          title: 'Site',
          is_active: true,
          sort_order: 1,
          questions: [
            {
              id: FIRST_QUESTION_ID,
              question_text: 'Van condition acceptable?',
              question_type: 'pass_fail',
              is_required: true,
              is_active: true,
              sort_order: 1,
              weight: 1,
              failure_triggers_action: false,
            },
            {
              id: SECOND_QUESTION_ID,
              question_text: 'Meter calibration in date?',
              question_type: 'pass_fail',
              is_required: true,
              is_active: true,
              sort_order: 2,
              weight: 1,
              failure_triggers_action: false,
            },
            {
              id: 153,
              question_text: 'Closing notes',
              question_type: 'text',
              is_required: false,
              is_active: true,
              sort_order: 3,
              weight: 1,
              failure_triggers_action: false,
            },
          ],
        },
      ],
    },
  })
}

/** Answer both pass_fail questions, landing on the trailing text question. */
async function answerBothQuestions() {
  renderPage()

  expect(await screen.findByText('Van condition acceptable?')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'PASS' }))
  await vi.advanceTimersByTimeAsync(700)

  expect(await screen.findByText('Meter calibration in date?')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'PASS' }))
  await vi.advanceTimersByTimeAsync(700)

  expect(await screen.findByText('Closing notes')).toBeInTheDocument()
}

function savedQuestionIds() {
  return mockUpsertByQuestion.mock.calls.map((call) => call[1])
}

describe('AuditExecution per-question saves (AUD-F3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockExecutableAudit()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('still saves the other questions when one question is rejected', async () => {
    mockUpsertByQuestion.mockImplementation((_runId: number, questionId: number) => {
      if (questionId === FIRST_QUESTION_ID) {
        return Promise.reject({
          response: { status: 400, data: { error: { code: 'VALIDATION_ERROR' } } },
        })
      }
      return Promise.resolve({ data: { id: 900 + questionId } })
    })

    await answerBothQuestions()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(savedQuestionIds()).toContain(SECOND_QUESTION_ID)
    })
    expect(savedQuestionIds()).toContain(FIRST_QUESTION_ID)
    expect(await screen.findByText('Request failed')).toBeInTheDocument()
  })

  it('keeps the local draft when a question failed, and drops it only once all of them land', async () => {
    mockUpsertByQuestion.mockImplementation((_runId: number, questionId: number) => {
      if (questionId === FIRST_QUESTION_ID) {
        return Promise.reject({ response: { status: 400, data: {} } })
      }
      return Promise.resolve({ data: { id: 900 + questionId } })
    })

    await answerBothQuestions()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(savedQuestionIds()).toContain(SECOND_QUESTION_ID)
    })
    // The rejected answer only exists on this device, so the stash that
    // protects it must survive.
    expect(deleteAuditDraft).not.toHaveBeenCalled()

    mockUpsertByQuestion.mockImplementation((_runId: number, questionId: number) =>
      Promise.resolve({ data: { id: 900 + questionId } }),
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(deleteAuditDraft).toHaveBeenCalledWith(RUN_ID)
    })
  })

  it('saves execute answers by (run, question) rather than deciding insert vs update', async () => {
    mockUpsertByQuestion.mockImplementation((_runId: number, questionId: number) =>
      Promise.resolve({ data: { id: 900 + questionId } }),
    )

    await answerBothQuestions()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(savedQuestionIds().sort()).toEqual([FIRST_QUESTION_ID, SECOND_QUESTION_ID])
    })
    expect(mockUpsertByQuestion).toHaveBeenCalledWith(
      RUN_ID,
      FIRST_QUESTION_ID,
      expect.objectContaining({ response_value: 'pass', applicability: 'applicable' }),
    )
    expect(mockCreateResponse).not.toHaveBeenCalled()
    expect(mockUpdateResponse).not.toHaveBeenCalled()
  })

  /** Reach the summary screen and press submit, which saves and then completes. */
  async function submitAudit() {
    await answerBothQuestions()
    fireEvent.click(screen.getByRole('button', { name: /Finish/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Submit Audit' }))
  }

  it("sends the run etag the answer write returned when it completes the run", async () => {
    mockUpsertByQuestion.mockImplementation((_runId: number, questionId: number) =>
      Promise.resolve({ data: { id: 900 + questionId }, headers: { etag: '"run-token-7"' } }),
    )
    mockCompleteRun.mockResolvedValue({ data: {} })

    await submitAudit()

    await waitFor(() => {
      expect(mockCompleteRun).toHaveBeenCalledWith(RUN_ID, 'run-token-7')
    })
  })

  it("does not mistake the answer row's updated_at for the run's etag", async () => {
    // The answer row carries its own updated_at. Sending it as the run's
    // If-Match is the self-inflicted "updated on another device" AUD-F3 exists
    // to remove, so no readable ETag must mean no precondition at all.
    mockUpsertByQuestion.mockImplementation((_runId: number, questionId: number) =>
      Promise.resolve({ data: { id: 900 + questionId, updated_at: '2026-09-02T12:00:00Z' } }),
    )
    mockCompleteRun.mockResolvedValue({ data: {} })

    await submitAudit()

    await waitFor(() => {
      expect(mockCompleteRun).toHaveBeenCalledWith(RUN_ID, null)
    })
  })
})
