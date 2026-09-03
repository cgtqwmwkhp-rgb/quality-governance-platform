/**
 * AUD-F5: a field auditor gets a camera AND a library, and a capture writes a
 * real link.
 *
 * Two defects are pinned here.
 *
 * 1. `<input type="file" capture="environment">` is camera-only on iOS — the
 *    file picker never opens. One input with `capture` therefore removed "attach
 *    a photo I already have" from the execute UI for every iPhone in the field,
 *    while looking correct on desktop Chrome, where `capture` is ignored. So the
 *    library input must exist and must NOT carry `capture`.
 * 2. The capture used to go to the generic `POST /evidence-assets/upload`, which
 *    can only record which *run* a file belongs to. Which question it answered
 *    lived in a client-written list, and when that save failed the photo was in
 *    Azure with nothing pointing at it (AUD-2026-0087). The page must call the
 *    audit-scoped endpoint, with the current question's id, so the server writes
 *    the answer row and the join in one transaction.
 *
 * `MobileAuditExecution` is deliberately not involved: live execute is
 * `AuditExecution`.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { auditsApi } from '../../api/client'
import AuditExecution from '../AuditExecution'

const mockNavigate = vi.fn()
const mockGetRunDetail = vi.fn()
const mockGetTemplate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api/client', () => ({
  auditsApi: {
    getRunDetail: (...args: unknown[]) => mockGetRunDetail(...args),
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    startRun: vi.fn().mockResolvedValue({ data: {} }),
    acknowledgeRun: vi.fn().mockResolvedValue({ data: {} }),
    createResponse: vi.fn(),
    updateResponse: vi.fn(),
    upsertByQuestion: vi.fn().mockResolvedValue({ data: { id: 7 } }),
    completeRun: vi.fn(),
    uploadQuestionEvidence: vi.fn().mockResolvedValue({
      data: {
        evidence_asset_id: 501,
        response_id: 7,
        run_id: 42,
        question_id: 151,
        role: 'photo',
        evidence_asset_ids: [501],
      },
    }),
  },
  evidenceAssetsApi: {
    upload: vi.fn(),
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
  saveAuditDraft: vi.fn(),
}))

const RUN_ID = 42
const QUESTION_ID = 151

function mockPhotoRun() {
  mockGetRunDetail.mockResolvedValue({
    data: {
      id: RUN_ID,
      reference_number: 'AUD-2026-0087',
      template_id: 12,
      template_version: 1,
      title: 'Site walk',
      status: 'in_progress',
      responses: [],
      findings: [],
      completion_percentage: 0,
      created_at: '2026-03-24T10:05:00Z',
    },
  })
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
      auto_create_findings: false,
      is_active: true,
      is_published: true,
      sections: [
        {
          id: 6,
          title: 'Evidence',
          is_active: true,
          sort_order: 1,
          questions: [
            {
              id: QUESTION_ID,
              question_text: 'Photograph the guarding',
              question_type: 'photo',
              is_required: true,
              is_active: true,
              sort_order: 1,
              weight: 1,
            },
          ],
        },
      ],
    },
  })
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={[`/audits/${RUN_ID}/execute`]}>
      <Routes>
        <Route path="/audits/:auditId/execute" element={<AuditExecution />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AuditExecution capture — camera and library', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('offers both a camera control and a library control', async () => {
    mockPhotoRun()
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()

    expect(screen.getByRole('button', { name: 'Take photo' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose photo from library' })).toBeInTheDocument()
  })

  it('keeps capture=environment off the library input so the picker still opens', async () => {
    mockPhotoRun()
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()

    const camera = document.querySelector('[data-testid="audit-photo-camera-input"]')
    const library = document.querySelector('[data-testid="audit-photo-library-input"]')

    expect(camera).toHaveAttribute('capture', 'environment')
    expect(camera).toHaveAttribute('accept', 'image/*')
    expect(library).not.toHaveAttribute('capture')
    expect(library).toHaveAttribute('accept', 'image/*')
  })

  it.each([
    ['audit-photo-camera-input', 'camera'],
    ['audit-photo-library-input', 'library'],
  ])('uploads a %s pick through the audit-scoped endpoint', async (testId) => {
    mockPhotoRun()
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()

    const input = document.querySelector(`[data-testid="${testId}"]`) as HTMLInputElement
    const file = new File(['pixels'], 'guarding.png', { type: 'image/png' })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(auditsApi.uploadQuestionEvidence).toHaveBeenCalledWith(
        RUN_ID,
        QUESTION_ID,
        expect.any(File),
        expect.objectContaining({ title: expect.stringContaining(String(QUESTION_ID)) }),
      )
    })
    // The generic evidence upload cannot record the question, so nothing on the
    // execute photo path may fall back to it.
    const { evidenceAssetsApi } = await import('../../api/client')
    expect(evidenceAssetsApi.upload).not.toHaveBeenCalled()
  })
})
