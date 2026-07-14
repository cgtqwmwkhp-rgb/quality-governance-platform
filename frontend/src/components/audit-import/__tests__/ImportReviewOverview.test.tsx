import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ImportReviewOverview } from '../ImportReviewOverview'

const job = {
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
}

describe('ImportReviewOverview', () => {
  it('renders job reference and declared scheme labels', () => {
    render(
      <ImportReviewOverview
        job={job as never}
        drafts={[]}
        declaredProgramLabel="Achilles UVDB"
        declaredSourceOrigin="third_party"
        declaredScheme="Achilles UVDB"
        resolvedTemplateName="Template"
        resolvedTemplateId={11}
        resolvedTemplateVersion={3}
        declaredExternalBody={null}
        declaredExternalReference={null}
        approvedCount={0}
        promoteableCount={0}
        isProcessing={false}
        lastUpdatedAt={null}
        isDocumentHidden={false}
      />,
    )

    expect(screen.getByText(/IMP-00072/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Achilles UVDB/i).length).toBeGreaterThan(0)
  })

  it('shows promotion progress and lease recovery guidance', () => {
    render(
      <ImportReviewOverview
        job={{ ...job, status: 'promoting', promote_total: 4, promote_succeeded: 2 } as never}
        drafts={[]}
        declaredProgramLabel="Achilles UVDB"
        declaredSourceOrigin="third_party"
        declaredScheme="Achilles UVDB"
        resolvedTemplateName="Template"
        resolvedTemplateId={11}
        resolvedTemplateVersion={3}
        declaredExternalBody={null}
        declaredExternalReference={null}
        approvedCount={2}
        promoteableCount={2}
        isProcessing={false}
        lastUpdatedAt={new Date('2026-07-14T12:00:00Z')}
        isDocumentHidden={false}
      />,
    )

    expect(screen.getByText(/2 of 4 materialized/i)).toBeInTheDocument()
    expect(screen.getByText(/expired worker lease returns accepted drafts/i)).toBeInTheDocument()
  })
})
