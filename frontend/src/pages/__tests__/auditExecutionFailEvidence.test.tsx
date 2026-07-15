import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AuditExecution, {
  FAIL_EVIDENCE_ERROR_MESSAGE,
  canAdvancePastFailEvidenceGate,
  isFailEvidenceGateActive,
  isQuestionFinding,
  questionCanRequireFailEvidence,
  shouldShowFailEvidencePanel,
} from '../AuditExecution'

const mockNavigate = vi.fn()
const mockGetRunDetail = vi.fn()
const mockGetTemplate = vi.fn()
const mockStartRun = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api/client', () => ({
  auditsApi: {
    getRunDetail: (...args: unknown[]) => mockGetRunDetail(...args),
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    startRun: (...args: unknown[]) => mockStartRun(...args),
    createResponse: vi.fn(),
    updateResponse: vi.fn(),
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}))

vi.mock('../../services/auditDraftStore', () => ({
  registerDraftSnapshot: vi.fn(),
  getAuditDraft: vi.fn().mockResolvedValue(null),
  deleteAuditDraft: vi.fn(),
  saveAuditDraft: vi.fn(),
}))

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/audits/42/execute']}>
      <Routes>
        <Route path="/audits/:auditId/execute" element={<AuditExecution />} />
      </Routes>
    </MemoryRouter>,
  )
}

const passFailQuestion = {
  id: 9,
  question_text: 'Fire extinguisher present?',
  question_type: 'pass_fail',
  is_required: true,
  is_active: true,
  sort_order: 1,
  weight: 1,
  failure_triggers_action: true,
  evidence_requirements: { required: false },
}

const secondQuestion = {
  id: 10,
  question_text: 'Inspection notes',
  question_type: 'text',
  is_required: false,
  is_active: true,
  sort_order: 2,
  weight: 1,
  failure_triggers_action: false,
}

function mockExecutableAudit() {
  const initialRun = {
    id: 42,
    reference_number: 'AUD-00042',
    template_id: 12,
    template_version: 1,
    title: 'Site walk',
    location: 'Yard',
    status: 'in_progress',
    responses: [],
    findings: [],
    completion_percentage: 0,
    created_at: '2026-03-24T10:05:00Z',
  }
  mockGetRunDetail.mockResolvedValue({ data: initialRun })
  mockGetTemplate.mockResolvedValue({
    data: {
      id: 12,
      name: 'Site walk',
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
          title: 'Safety',
          is_active: true,
          sort_order: 1,
          questions: [passFailQuestion, secondQuestion],
        },
      ],
    },
  })
  mockStartRun.mockResolvedValue({ data: {} })
}

describe('fail evidence gate helpers', () => {
  const baseQuestion = {
    type: 'pass_fail',
    evidenceRequired: false,
    failureTriggersAction: true,
  }

  it('detects findings for fail and inverted pass', () => {
    expect(isQuestionFinding(baseQuestion, 'fail')).toBe(true)
    expect(isQuestionFinding(baseQuestion, 'pass')).toBe(false)
    expect(
      isQuestionFinding({ ...baseQuestion, positiveAnswer: 'no' }, 'pass'),
    ).toBe(true)
  })

  it('activates gate only when finding lacks photos and policy requires evidence', () => {
    expect(
      isFailEvidenceGateActive(baseQuestion, { response: 'fail', photos: [] }),
    ).toBe(true)
    expect(
      isFailEvidenceGateActive(baseQuestion, { response: 'fail', photos: ['data:image/png;base64,x'] }),
    ).toBe(false)
    expect(
      isFailEvidenceGateActive(
        { ...baseQuestion, failureTriggersAction: false, evidenceRequired: false },
        { response: 'fail' },
      ),
    ).toBe(false)
    expect(questionCanRequireFailEvidence({ ...baseQuestion, evidenceRequired: true })).toBe(true)
  })

  it('shows evidence panel for configured or fail-triggered questions', () => {
    expect(
      shouldShowFailEvidencePanel(
        { type: 'pass_fail', evidenceRequired: true, failureTriggersAction: false },
        undefined,
      ),
    ).toBe(true)
    expect(
      shouldShowFailEvidencePanel(baseQuestion, { response: 'fail' }),
    ).toBe(true)
    expect(
      shouldShowFailEvidencePanel(baseQuestion, { response: 'pass' }),
    ).toBe(false)
    expect(canAdvancePastFailEvidenceGate(baseQuestion, { response: 'pass' })).toBe(true)
  })
})

describe('AuditExecution fail evidence gate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('blocks auto-advance on FAIL until photo evidence is attached', async () => {
    mockExecutableAudit()
    renderPage()

    expect(await screen.findByText('Fire extinguisher present?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'FAIL' }))

    await vi.advanceTimersByTimeAsync(700)

    expect(screen.getByText('Fire extinguisher present?')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(FAIL_EVIDENCE_ERROR_MESSAGE)
    expect(screen.getByRole('button', { name: 'Take photo or upload evidence' })).toHaveAttribute(
      'aria-invalid',
      'true',
    )

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['pixels'], 'evidence.png', { type: 'image/png' })
    fireEvent.change(fileInput, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByAltText('Evidence 1')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText('Inspection notes')).toBeInTheDocument()
  })

  it('auto-advances on PASS without requiring evidence', async () => {
    mockExecutableAudit()
    renderPage()

    expect(await screen.findByText('Fire extinguisher present?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'PASS' }))

    await vi.advanceTimersByTimeAsync(700)

    expect(await screen.findByText('Inspection notes')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
