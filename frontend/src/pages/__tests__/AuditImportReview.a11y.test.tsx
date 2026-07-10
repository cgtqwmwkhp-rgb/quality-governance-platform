/**
 * Real axe coverage for the Audit Import Review CUJ page (/import-review), not a route stub.
 * Complements stub-based pages-a11y.test.tsx (stub removed for this route) and the
 * Playwright a11y-audit E2E suite.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import AuditImportReview from '../AuditImportReview'
import { expectNoA11yViolations } from '../../test/axe-helper'

const mockGetJob = vi.fn()
const mockGetLatestJobForRun = vi.fn()
const mockGetRunDetail = vi.fn()
const mockListDrafts = vi.fn()
const mockGetReconciliation = vi.fn()

vi.mock('../../api/client', () => ({
  ErrorClass: {
    VALIDATION_ERROR: 'VALIDATION_ERROR',
    AUTH_ERROR: 'AUTH_ERROR',
    NOT_FOUND: 'NOT_FOUND',
    WRITE_BLOCKED: 'WRITE_BLOCKED',
    NETWORK_ERROR: 'NETWORK_ERROR',
    SERVER_ERROR: 'SERVER_ERROR',
    SETUP_REQUIRED: 'SETUP_REQUIRED',
    UNKNOWN: 'UNKNOWN',
  },
  createApiError: (error: { response?: { status?: number; data?: { detail?: { message?: string } | string } } }) => {
    const status = error?.response?.status
    let errorClass = 'UNKNOWN'
    if (status === 400 || status === 422) errorClass = 'VALIDATION_ERROR'
    else if (status === 401 || status === 403) errorClass = 'AUTH_ERROR'
    else if (status === 404) errorClass = 'NOT_FOUND'
    else if ((status ?? 0) >= 500) errorClass = 'SERVER_ERROR'
    const detail = error?.response?.data?.detail
    return {
      error_class: errorClass,
      status_code: status,
      detail: typeof detail === 'string' ? detail : detail?.message,
    }
  },
  getApiErrorMessage: (error: { response?: { data?: { detail?: { message?: string } | string } }; message?: string }) => {
    const detail = error?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail && typeof detail === 'object' && 'message' in detail) return detail.message
    return error?.message || 'API Error'
  },
  auditsApi: {
    getRunDetail: (...args: unknown[]) => mockGetRunDetail(...args),
  },
  externalAuditImportsApi: {
    getJob: (...args: unknown[]) => mockGetJob(...args),
    getLatestJobForRun: (...args: unknown[]) => mockGetLatestJobForRun(...args),
    listDrafts: (...args: unknown[]) => mockListDrafts(...args),
    getReconciliation: (...args: unknown[]) => mockGetReconciliation(...args),
    queueJob: vi.fn(),
    processJob: vi.fn(),
    reviewDraft: vi.fn(),
    bulkReviewJob: vi.fn(),
    promoteJob: vi.fn(),
  },
}))

function renderPage(initialEntry = '/audits/41/import-review?jobId=72') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/audits/:auditId/import-review" element={<AuditImportReview />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Audit Import Review page accessibility (CUJ real page /import-review)', () => {
  afterEach(() => {
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      get: () => false,
    })
  })

  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      get: () => false,
    })
    mockGetReconciliation.mockResolvedValue({ data: null })
    mockGetLatestJobForRun.mockResolvedValue({ data: null })
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'review_required',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
        analysis_summary: 'Review required',
        promotion_summary_json: null,
        positive_summary_json: [],
        nonconformity_summary_json: [],
        improvement_summary_json: [],
        evidence_preview_json: [],
        processing_warnings_json: [],
        provenance_json: {
          processing_template_id: 11,
          processing_template_version: 3,
          declared_source_origin: 'third_party',
          declared_assurance_scheme: 'Achilles UVDB',
        },
      },
    })
    mockGetRunDetail.mockResolvedValue({
      data: {
        id: 41,
        reference_number: 'AUD-00041',
        template_id: 11,
        template_version: 3,
        template_name: 'External Audit Intake',
        title: 'Achilles follow-up audit',
        source_origin: 'third_party',
        assurance_scheme: 'Achilles UVDB',
        external_body_name: 'Achilles',
        external_reference: 'UVDB-2026-001',
        status: 'completed',
        is_external_audit_import: true,
        responses: [],
        findings: [],
        completion_percentage: 0,
        created_at: '2026-03-24T10:00:00Z',
      },
    })
    mockListDrafts.mockResolvedValue({
      data: [
        {
          id: 11,
          import_job_id: 72,
          audit_run_id: 41,
          status: 'draft',
          title: 'Needs follow-up',
          description: 'Evidence snippet',
          severity: 'high',
          finding_type: 'nonconformity',
          confidence_score: 0.88,
          competence_verdict: null,
          evidence_snippets_json: ['Evidence snippet'],
          mapped_frameworks_json: [{ framework: 'Achilles UVDB' }],
          mapped_standards_json: [{ standard: 'ISO 9001', clause_number: '8.1' }],
          suggested_action_title: 'Address issue',
          suggested_risk_title: 'Create risk',
        },
      ],
    })
  })

  it('renders the real Audit Import Review page with a pending draft without critical axe violations', async () => {
    const { container } = renderPage()

    await waitFor(() => {
      expect(screen.getByText('Needs follow-up')).toBeInTheDocument()
    })

    await expectNoA11yViolations(container)
  })

  it('renders the empty/no-drafts state without critical axe violations', async () => {
    mockListDrafts.mockResolvedValue({ data: [] })
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'review_required',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
        analysis_summary: 'Review required',
        promotion_summary_json: null,
        positive_summary_json: [],
        nonconformity_summary_json: [],
        improvement_summary_json: [],
        evidence_preview_json: [],
        processing_warnings_json: [],
        provenance_json: {
          processing_template_id: 11,
          processing_template_version: 3,
          declared_source_origin: 'third_party',
          declared_assurance_scheme: 'Achilles UVDB',
        },
      },
    })

    const { container } = renderPage()

    await waitFor(() => {
      expect(screen.getByText('IMP-00072')).toBeInTheDocument()
    })

    await expectNoA11yViolations(container)
  })
})
