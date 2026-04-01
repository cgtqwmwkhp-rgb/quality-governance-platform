import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuditImportReview from '../AuditImportReview'

const mockGetJob = vi.fn()
const mockGetLatestJobForRun = vi.fn()
const mockGetRunDetail = vi.fn()
const mockListDrafts = vi.fn()
const mockGetReconciliation = vi.fn()
const mockQueueJob = vi.fn()
const mockProcessJob = vi.fn()
const mockReviewDraft = vi.fn()
const mockPromoteJob = vi.fn()

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
    queueJob: (...args: unknown[]) => mockQueueJob(...args),
    processJob: (...args: unknown[]) => mockProcessJob(...args),
    reviewDraft: (...args: unknown[]) => mockReviewDraft(...args),
    promoteJob: (...args: unknown[]) => mockPromoteJob(...args),
  },
}))

function renderPage(initialEntry = '/audits/41/import-review?jobId=72') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/audits/:auditId/import-review" element={<AuditImportReview />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AuditImportReview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetReconciliation.mockResolvedValue({ data: null })
    mockGetLatestJobForRun.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'review_required',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
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
  })

  it('blocks mismatched audit routes from showing the wrong import job', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'review_required',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
        provenance_json: {
          processing_template_id: 11,
          processing_template_version: 3,
          declared_source_origin: 'third_party',
          declared_assurance_scheme: 'Achilles UVDB',
        },
      },
    })
    mockListDrafts.mockResolvedValue({ data: [] })

    renderPage('/audits/99/import-review?jobId=72')

    expect(
      await screen.findByText(
        'This import job belongs to a different audit run. Re-open it from the audits workspace.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open Compliance Summary' })).toBeDisabled()
    expect(mockGetRunDetail).not.toHaveBeenCalled()
  })

  it('resolves the latest job for a run when no job query string is present', async () => {
    mockListDrafts.mockResolvedValue({ data: [] })

    renderPage('/audits/41/import-review')

    expect(await screen.findByText('IMP-00072')).toBeInTheDocument()
    expect(mockGetLatestJobForRun).toHaveBeenCalledWith(41)
    expect(mockGetJob).not.toHaveBeenCalled()
  })

  it('shows failed-job diagnostics and counts clause mappings without clause ids', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'failed',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
        analysis_summary: 'Review required',
        promotion_summary_json: null,
        positive_summary_json: [],
        nonconformity_summary_json: [],
        improvement_summary_json: [],
        evidence_preview_json: [],
        processing_warnings_json: [],
        provider_name: 'mistral',
        provider_model: 'mistral-ocr-latest',
        source_filename: 'achilles-audit.pdf',
        extraction_method: 'ocr',
        detected_scheme: 'achilles_uvdb',
        detected_scheme_confidence: 0.91,
        error_code: 'IMPORT_PROCESSING_FAILED',
        error_detail:
          'Import analysis failed before review could begin. Review logs and retry the job.',
      },
    })
    mockListDrafts.mockResolvedValue({
      data: [
        {
          id: 11,
          import_job_id: 72,
          audit_run_id: 41,
          status: 'promoted',
          title: 'Achilles: Major non-conformance',
          description: 'Evidence snippet',
          severity: 'critical',
          finding_type: 'nonconformity',
          confidence_score: 0.91,
          competence_verdict: null,
          evidence_snippets_json: ['Evidence snippet'],
          mapped_frameworks_json: [{ framework: 'Achilles UVDB' }],
          mapped_standards_json: [{ standard: 'ISO 9001', clause_number: '8.1' }],
          suggested_action_title: 'Address imported audit issue',
          suggested_risk_title: 'Imported audit escalation',
        },
      ],
    })

    renderPage()

    expect(await screen.findByText('Import failed')).toBeInTheDocument()
    expect(screen.getByText('Declared intake').parentElement).toHaveTextContent('Achilles / UVDB')
    expect(screen.getByText('Processing template').parentElement).toHaveTextContent(
      'External Audit Intake',
    )
    expect(screen.getByText('Processing template').parentElement).toHaveTextContent('Version 3')
    expect(screen.getByText('Source file').parentElement).toHaveTextContent('achilles-audit.pdf')
    expect(screen.getByText('OCR provider').parentElement).toHaveTextContent('mistral')
    expect(screen.getByText('Classification').parentElement).toHaveTextContent('achilles uvdb')
    expect(screen.getByText('Classification').parentElement).toHaveTextContent('91% confidence')
    expect(screen.getByText('IMPORT_PROCESSING_FAILED')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Import analysis failed before review could begin. Review logs and retry the job.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('critical').className).toContain('bg-red-100')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Promote Accepted Drafts' })).toBeDisabled()
    })

    expect(screen.getByText('ISO evidence links').parentElement).toHaveTextContent('1')
  })

  it('keeps drafts visible after review errors and clears the error after a successful retry', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'review_required',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
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
    mockReviewDraft.mockRejectedValueOnce(new Error('temporary failure')).mockResolvedValueOnce({
      data: {
        id: 11,
        import_job_id: 72,
        audit_run_id: 41,
        status: 'accepted',
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
    })

    renderPage()

    expect(await screen.findByText('Needs follow-up')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Accept finding/i }))

    expect(await screen.findByText('Failed to update the draft. Please retry.')).toBeInTheDocument()
    expect(screen.getByText('Needs follow-up')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^Accept finding/i }))

    await waitFor(() => {
      expect(
        screen.queryByText('Failed to update the draft. Please retry.'),
      ).not.toBeInTheDocument()
    })
    expect(screen.getByText('accepted')).toBeInTheDocument()
  })

  it('shows downstream workflow proof from reconciliation data', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'completed',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
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
    mockListDrafts.mockResolvedValue({ data: [] })
    mockGetReconciliation.mockResolvedValue({
      data: {
        job_id: 72,
        audit_run_id: 41,
        audit_reference: 'AUD-00041',
        job_status: 'completed',
        canonical_read_model: 'specialist_sync_verification',
        specialist_home: { path: '/uvdb', label: 'Achilles / UVDB' },
        accepted_total: 1,
        promoted_total: 1,
        accepted_pending_total: 0,
        failed_total: 0,
        failed_drafts: [],
        materialized: {
          audit_findings: 1,
          capa_actions: 1,
          enterprise_risks: 1,
          uvdb_audit_id: 18,
          external_audit_record_id: 22,
        },
        proof_matrix: [
          { step: 'upload', status: 'ok', detail: 'report.pdf' },
          { step: 'promotion', status: 'ok', detail: '1 finding(s) materialized' },
        ],
        draft_results: [],
        view_links: {
          actions: '/actions?sourceType=audit_finding',
          risk_register: '/risk-register?auditOnly=1&auditRef=AUD-00041',
          uvdb: '/uvdb?auditRef=AUD-00041',
        },
      },
    })

    renderPage()

    expect(await screen.findByText('Downstream Workflow Proof')).toBeInTheDocument()
    expect(screen.getByText(/Canonical read model:\s*specialist sync verification\./i)).toBeInTheDocument()
    expect(screen.getByText('CAPA Actions')).toBeInTheDocument()
    expect(screen.getByText('Enterprise Risks')).toBeInTheDocument()
    expect(screen.getByText('View Audit Actions')).toBeInTheDocument()
  })

  it('surfaces a reconciliation compatibility warning when diagnostics are unavailable', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'review_required',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
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
    mockListDrafts.mockResolvedValue({ data: [] })
    mockGetReconciliation.mockRejectedValue({ response: { status: 404, data: { detail: 'missing' } } })

    renderPage()

    expect(
      await screen.findByText(
        'Downstream workflow diagnostics are unavailable for this job on the current backend.',
      ),
    ).toBeInTheDocument()
  })

  it('shows the backend validation message when promotion fails', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'review_required',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
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
    mockListDrafts.mockResolvedValue({
      data: [
        {
          id: 11,
          import_job_id: 72,
          audit_run_id: 41,
          status: 'accepted',
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
    mockPromoteJob.mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: {
            message:
              'External audit imports require an active tenant context. Assign the user to a tenant and retry.',
          },
        },
      },
    })

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Promote Accepted Drafts' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Promote' }))

    expect(
      await screen.findByText(
        'External audit imports require an active tenant context. Assign the user to a tenant and retry.',
      ),
    ).toBeInTheDocument()
  })

  it('shows queue recovery guidance and retries queueing pending imports', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'pending',
        specialist_home_path: '/uvdb',
        specialist_home_label: 'Open Achilles / UVDB',
        analysis_summary: null,
        promotion_summary_json: null,
        positive_summary_json: [],
        nonconformity_summary_json: [],
        improvement_summary_json: [],
        evidence_preview_json: [],
        processing_warnings_json: [],
        error_code: 'QUEUE_DISPATCH_FAILED',
        error_detail: 'Background processing could not be started. Retry queueing the import.',
        provenance_json: {
          processing_template_id: 11,
          processing_template_version: 3,
          declared_source_origin: 'third_party',
          declared_assurance_scheme: 'Achilles UVDB',
        },
      },
    })
    mockListDrafts.mockResolvedValue({ data: [] })
    mockQueueJob.mockResolvedValue({ data: { id: 72, status: 'queued' } })
    mockProcessJob.mockResolvedValue({ data: { id: 72, status: 'review_required' } })

    renderPage('/audits/41/import-review?jobId=72&queueError=1')

    expect(
      await screen.findByText(
        'The import workspace is ready, but automatic processing did not start. Retry queueing below.',
      ),
    ).toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button', { name: 'Retry Queue' })[0]!)

    await waitFor(() => {
      expect(mockQueueJob).toHaveBeenCalledWith(72)
    })
  })
})
