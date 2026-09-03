/**
 * AUD-F6 on the screen the auditor is actually looking at.
 *
 * The store tests prove the ledger behaves; these prove the page *says so*. That
 * is the whole defect: `saveAuditDraft` used to catch `QuotaExceeded` and return
 * `false`, and every call site did `void saveAuditDraft(...)`, so a tablet with a
 * full disk drew exactly the same screen as a working one. `persist()` was never
 * called at all, so nothing ever admitted that the browser had made no promise
 * to keep the answers.
 *
 * `MobileAuditExecution` is deliberately not involved: live execute is
 * `AuditExecution`.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AuditExecution from '../AuditExecution'
import {
  deleteCaptureBlob,
  ensureDeviceLedgerDurability,
  putCaptureBlob,
  saveAuditDraft,
  type DeviceLedgerStatus,
} from '../../services/auditDraftStore'

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
      data: { evidence_asset_id: 501, response_id: 7, evidence_asset_ids: [501] },
    }),
  },
  evidenceAssetsApi: {
    upload: vi.fn(),
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    getSignedUrl: vi.fn(),
    getContent: vi.fn().mockResolvedValue({ data: new Blob(['photo-bytes']) }),
    delete: vi.fn().mockResolvedValue({}),
  },
  getApiErrorMessage: (error: unknown, fallback?: string) =>
    error instanceof Error ? error.message : (fallback ?? 'Request failed'),
}))

const DURABLE: DeviceLedgerStatus = {
  durable: true,
  reason: 'ok',
  message: '',
  writeFailed: false,
  usageBytes: null,
  quotaBytes: null,
}

/** Subscribers registered by the page, so a test can publish a status change. */
const ledgerSubscribers = new Set<(next: DeviceLedgerStatus) => void>()

vi.mock('../../services/auditDraftStore', () => ({
  registerDraftSnapshot: vi.fn(() => () => {}),
  getAuditDraft: vi.fn().mockResolvedValue(null),
  deleteAuditDraft: vi.fn(),
  saveAuditDraft: vi.fn().mockResolvedValue({ ok: true }),
  putCaptureBlob: vi.fn().mockResolvedValue({ ok: true }),
  deleteCaptureBlob: vi.fn().mockResolvedValue(undefined),
  listCaptureBlobs: vi.fn().mockResolvedValue([]),
  ensureDeviceLedgerDurability: vi.fn(),
  subscribeDeviceLedgerStatus: vi.fn((listener: (next: DeviceLedgerStatus) => void) => {
    ledgerSubscribers.add(listener)
    return () => ledgerSubscribers.delete(listener)
  }),
  getDeviceLedgerStatus: vi.fn(() => DURABLE),
}))

vi.mock('../../services/deviceLedgerIdentity', () => ({
  primeDeviceLedgerIdentity: vi.fn().mockResolvedValue({ tenantId: 7, userId: 5 }),
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
      created_at: '2026-09-03T09:00:00Z',
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

describe('AuditExecution device ledger (AUD-F6)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ledgerSubscribers.clear()
    vi.mocked(ensureDeviceLedgerDurability).mockResolvedValue(DURABLE)
    vi.mocked(saveAuditDraft).mockResolvedValue({ ok: true })
    vi.mocked(putCaptureBlob).mockResolvedValue({ ok: true })
  })

  it('says nothing about durability when the browser granted it', async () => {
    mockPhotoRun()
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()
    await waitFor(() => expect(ensureDeviceLedgerDurability).toHaveBeenCalled())

    expect(screen.queryByTestId('device-ledger-not-durable')).not.toBeInTheDocument()
    expect(screen.queryByTestId('device-ledger-write-failed')).not.toBeInTheDocument()
  })

  it('tells the auditor the audit is not durable here when persist() is denied', async () => {
    vi.mocked(ensureDeviceLedgerDurability).mockResolvedValue({
      durable: false,
      reason: 'persist-denied',
      message:
        'This audit is not durable on this device: the browser refused durable storage and may clear these answers without warning. Press Save while you have signal.',
      writeFailed: false,
      usageBytes: 1_024,
      quotaBytes: 2_048,
    })
    mockPhotoRun()
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()

    const banner = await screen.findByTestId('device-ledger-not-durable')
    expect(banner).toHaveTextContent('not durable on this device')
    // Nothing in this slice replays a write, so the copy must not imply one.
    expect(banner.textContent ?? '').not.toMatch(/will sync|syncing|synced/i)
  })

  it('blocks with an alert when a ledger write actually failed on quota', async () => {
    mockPhotoRun()
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()
    await waitFor(() => expect(ledgerSubscribers.size).toBeGreaterThan(0))

    // What the store publishes when a put throws QuotaExceededError.
    for (const listener of ledgerSubscribers) {
      listener({
        durable: false,
        reason: 'quota-exceeded',
        message:
          'Device storage is full — this answer was NOT saved on this device. Free up space, then press Save while you have signal.',
        writeFailed: true,
        usageBytes: 5,
        quotaBytes: 5,
      })
    }

    const alert = await screen.findByTestId('device-ledger-write-failed')
    expect(alert).toHaveAttribute('role', 'alert')
    expect(alert).toHaveTextContent('NOT saved on this device')
    // A failed write is one fact and an unpromising browser is another; only the
    // blocking one shows when both are true.
    expect(screen.queryByTestId('device-ledger-not-durable')).not.toBeInTheDocument()
  })

  it('writes the capture bytes once, before the upload, and drops them on ACK', async () => {
    mockPhotoRun()
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()

    const input = document.querySelector(
      '[data-testid="audit-photo-camera-input"]',
    ) as HTMLInputElement
    fireEvent.change(input, {
      target: { files: [new File(['pixels'], 'guarding.png', { type: 'image/png' })] },
    })

    await waitFor(() => expect(putCaptureBlob).toHaveBeenCalledTimes(1))
    const written = vi.mocked(putCaptureBlob).mock.calls[0][0]
    expect(written).toMatchObject({
      runId: RUN_ID,
      questionId: String(QUESTION_ID),
      kind: 'photo',
    })
    expect(written.captureId).toBeTruthy()

    // Bytes reach the device before the request, so an upload that never lands
    // still leaves a photo the auditor can see and re-send.
    const { auditsApi } = await import('../../api/client')
    await waitFor(() => expect(auditsApi.uploadQuestionEvidence).toHaveBeenCalled())

    // ...and once the server holds it, this store is not the photo SSOT.
    await waitFor(() =>
      expect(deleteCaptureBlob).toHaveBeenCalledWith(RUN_ID, written.captureId),
    )
    expect(putCaptureBlob).toHaveBeenCalledTimes(1)
  })

  it('keeps the capture bytes when the upload fails', async () => {
    mockPhotoRun()
    const { auditsApi } = await import('../../api/client')
    vi.mocked(auditsApi.uploadQuestionEvidence).mockRejectedValueOnce(new Error('offline'))
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()

    const input = document.querySelector(
      '[data-testid="audit-photo-camera-input"]',
    ) as HTMLInputElement
    fireEvent.change(input, {
      target: { files: [new File(['pixels'], 'guarding.png', { type: 'image/png' })] },
    })

    await waitFor(() => expect(putCaptureBlob).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.getByText('offline')).toBeInTheDocument())
    // The photo only exists on this device, so the ledger copy has to survive.
    expect(deleteCaptureBlob).not.toHaveBeenCalled()
  })
})
