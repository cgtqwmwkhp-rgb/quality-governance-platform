import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ImportReviewEvidenceCard } from '../ImportReviewEvidenceCard'

const jobWithEvidence = {
  id: 88,
  evidence_preview_json: [
    { clause_number: '8.5.1', standard: 'ISO 9001' },
    { clause_id: 'A.5.1', standard: 'ISO 27001' },
  ],
  positive_summary_json: [{ id: 1 }],
  nonconformity_summary_json: [{ id: 2 }, { id: 3 }],
  improvement_summary_json: [],
}

describe('ImportReviewEvidenceCard', () => {
  it('renders evidence badges, counts, and promotion impact', () => {
    render(
      <ImportReviewEvidenceCard
        job={jobWithEvidence as never}
        approvedCount={4}
        acceptedClauseCount={2}
        acceptedActionCandidates={1}
        acceptedRiskCandidates={0}
        schemeAlignment={{ status: 'aligned', reason: 'Scheme matches' }}
      />,
    )

    expect(screen.getByText('Evidence and mappings')).toBeInTheDocument()
    expect(screen.getByText(/8\.5\.1\s+ISO 9001/)).toBeInTheDocument()
    expect(screen.getByText(/A\.5\.1\s+ISO 27001/)).toBeInTheDocument()
    expect(screen.getByText('Positive evidence')).toBeInTheDocument()
    expect(screen.getByText('Non-compliances')).toBeInTheDocument()
    expect(screen.getByText('Improvements')).toBeInTheDocument()
    expect(screen.getByText('Promotion impact')).toBeInTheDocument()
    expect(screen.getByText('Accepted findings')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('aligned')).toBeInTheDocument()
    expect(screen.getByText('Scheme matches')).toBeInTheDocument()
  })

  it('shows empty-state copy when no evidence preview exists', () => {
    render(
      <ImportReviewEvidenceCard
        job={
          {
            id: 1,
            evidence_preview_json: [],
            positive_summary_json: [],
            nonconformity_summary_json: [],
            improvement_summary_json: [],
          } as never
        }
        approvedCount={0}
        acceptedClauseCount={0}
        acceptedActionCandidates={0}
        acceptedRiskCandidates={0}
      />,
    )

    expect(screen.getByTestId('import-review-evidence-empty')).toBeInTheDocument()
    expect(screen.getByText('No clause-level evidence preview yet')).toBeInTheDocument()
    expect(
      screen.getByText(/Mappings appear after OCR\/analysis extracts clause references/i),
    ).toBeInTheDocument()
    expect(screen.queryByText('aligned')).not.toBeInTheDocument()
  })

  it('guides when summaries exist without clause badges', () => {
    render(
      <ImportReviewEvidenceCard
        job={
          {
            id: 2,
            evidence_preview_json: [],
            positive_summary_json: [{ id: 1 }],
            nonconformity_summary_json: [],
            improvement_summary_json: [],
          } as never
        }
        approvedCount={0}
        acceptedClauseCount={0}
        acceptedActionCandidates={0}
        acceptedRiskCandidates={0}
      />,
    )

    expect(screen.getByTestId('import-review-evidence-empty')).toBeInTheDocument()
    expect(
      screen.getByText(/Summary counts are available below/i),
    ).toBeInTheDocument()
  })
})
