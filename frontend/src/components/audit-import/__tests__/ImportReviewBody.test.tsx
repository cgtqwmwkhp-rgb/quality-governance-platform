import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ImportReviewBody } from '../ImportReviewBody'

vi.mock('../DraftFindingsList', () => ({
  DraftFindingsList: () => <div>Draft findings</div>,
}))
vi.mock('../DownstreamWorkflowProof', () => ({
  DownstreamWorkflowProof: () => <div>Downstream proof</div>,
  isCompleteReconciliation: () => false,
}))
vi.mock('../ImportReviewAuditSummary', () => ({
  ImportReviewAuditSummary: () => <div>Audit summary</div>,
}))
vi.mock('../ImportReviewEvidenceCard', () => ({
  ImportReviewEvidenceCard: () => <div>Evidence card</div>,
}))
vi.mock('../ImportReviewNotices', () => ({
  ImportReviewNotices: ({ section }: { section: string }) => (
    <div>Notices {section}</div>
  ),
}))
vi.mock('../ImportReviewOverview', () => ({
  ImportReviewOverview: () => <div>Overview</div>,
}))
vi.mock('../ImportReviewProcessingPanels', () => ({
  ImportReviewProcessingPanels: () => <div>Processing panels</div>,
}))
vi.mock('../ImportReviewPromoteBanner', () => ({
  ImportReviewPromoteBanner: () => <div>Promote banner</div>,
}))

const baseProps = {
  navigate: vi.fn(),
  job: {
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
    provenance_json: {},
  },
  drafts: [],
  reconciliation: null,
  error: null,
  queueNotice: null,
  reconciliationNotice: null,
  promotionFailedDrafts: [],
  lastUpdatedAt: null,
  isProcessing: false,
  isDocumentHidden: false,
  load: vi.fn(),
  approvedCount: 0,
  promoteableCount: 1,
  acceptedClauseCount: 0,
  acceptedActionCandidates: 0,
  acceptedRiskCandidates: 0,
  schemeAlignment: null,
  declaredProgramLabel: 'Achilles UVDB',
  declaredSourceOrigin: 'third_party',
  declaredScheme: 'Achilles UVDB',
  resolvedTemplateVersion: 3,
  resolvedTemplateId: 11,
  resolvedTemplateName: 'Template',
  declaredExternalBody: null,
  declaredExternalReference: null,
  specialistHome: { label: 'Open Achilles / UVDB', path: '/uvdb' },
  busyDraftId: null,
  isBulkReviewing: false,
  isPromoting: false,
  isQueueing: false,
  showPromoteConfirm: false,
  setShowPromoteConfirm: vi.fn(),
  successMessage: null,
  dismissSuccess: vi.fn(),
  handleDraftDecision: vi.fn(),
  handlePromoteClick: vi.fn(),
  handlePromoteConfirm: vi.fn(),
  handleRetryQueue: vi.fn(),
} as const

describe('ImportReviewBody', () => {
  it('renders promote banner, notices, overview, and draft list for a loaded job', () => {
    render(<ImportReviewBody {...(baseProps as never)} />)

    expect(screen.getByText('Promote banner')).toBeInTheDocument()
    expect(screen.getByText('Notices pre-proof')).toBeInTheDocument()
    expect(screen.getByText('Notices post-proof')).toBeInTheDocument()
    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.getByText('Audit summary')).toBeInTheDocument()
    expect(screen.getByText('Processing panels')).toBeInTheDocument()
    expect(screen.getByText('Evidence card')).toBeInTheDocument()
    expect(screen.getByText('Draft findings')).toBeInTheDocument()
  })

  it('omits overview and evidence when job is missing', () => {
    render(<ImportReviewBody {...(baseProps as never)} job={null} />)

    expect(screen.getByText('Promote banner')).toBeInTheDocument()
    expect(screen.queryByText('Overview')).not.toBeInTheDocument()
    expect(screen.queryByText('Evidence card')).not.toBeInTheDocument()
    expect(screen.getByText('Draft findings')).toBeInTheDocument()
  })
})
