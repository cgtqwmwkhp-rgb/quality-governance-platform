import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuditImportReview from '../AuditImportReview'

const mockGetJob = vi.fn()
const mockListDrafts = vi.fn()
const mockReviewDraft = vi.fn()
const mockPromoteJob = vi.fn()

vi.mock('../../api/client', () => ({
  externalAuditImportsApi: {
    getJob: (...args: unknown[]) => mockGetJob(...args),
    listDrafts: (...args: unknown[]) => mockListDrafts(...args),
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
  })

  it('blocks mismatched audit routes from showing the wrong import job', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'review_required',
      },
    })
    mockListDrafts.mockResolvedValue({ data: [] })

    renderPage('/audits/99/import-review?jobId=72')

    expect(
      await screen.findByText('This import job belongs to a different audit run. Re-open it from the audits workspace.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open Audit Run' })).toBeDisabled()
  })

  it('shows failed-job diagnostics and counts clause mappings without clause ids', async () => {
    mockGetJob.mockResolvedValue({
      data: {
        id: 72,
        audit_run_id: 41,
        reference_number: 'IMP-00072',
        status: 'failed',
        analysis_summary: 'Review required',
        promotion_summary_json: null,
        positive_summary_json: [],
        nonconformity_summary_json: [],
        improvement_summary_json: [],
        evidence_preview_json: [],
        processing_warnings_json: [],
        error_code: 'IMPORT_PROCESSING_FAILED',
        error_detail: 'Import analysis failed before review could begin. Review logs and retry the job.',
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
    expect(screen.getByText('IMPORT_PROCESSING_FAILED')).toBeInTheDocument()
    expect(
      screen.getByText('Import analysis failed before review could begin. Review logs and retry the job.'),
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
        promotion_summary_json: null,
        positive_summary_json: [],
        nonconformity_summary_json: [],
        improvement_summary_json: [],
        evidence_preview_json: [],
        processing_warnings_json: [],
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
    mockReviewDraft
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce({
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
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }))

    expect(await screen.findByText('Failed to update the draft. Please retry.')).toBeInTheDocument()
    expect(screen.getByText('Needs follow-up')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Accept' }))

    await waitFor(() => {
      expect(screen.queryByText('Failed to update the draft. Please retry.')).not.toBeInTheDocument()
    })
    expect(screen.getByText('accepted')).toBeInTheDocument()
  })
})
