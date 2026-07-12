import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PromotionImpactPanel } from '../PromotionImpactPanel'

describe('PromotionImpactPanel', () => {
  it('renders accepted finding and candidate counts', () => {
    render(
      <PromotionImpactPanel
        approvedCount={4}
        acceptedClauseCount={7}
        acceptedActionCandidates={2}
        acceptedRiskCandidates={1}
        schemeAlignment={{ status: 'aligned', reason: 'UVDB mapped' }}
      />,
    )
    expect(screen.getByText('Promotion impact')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText(/aligned/i)).toBeInTheDocument()
    expect(screen.getByText('UVDB mapped')).toBeInTheDocument()
  })

  it('shows ≤2-click attest next-step when accepted findings are ready', () => {
    render(
      <PromotionImpactPanel
        approvedCount={3}
        acceptedClauseCount={1}
        acceptedActionCandidates={1}
        acceptedRiskCandidates={0}
      />,
    )
    expect(screen.getByTestId('import-review-impact-attest-next')).toHaveTextContent(
      /Promote Now, then Confirm — two clicks to attest/i,
    )
  })

  it('hides attest next-step when no accepted findings', () => {
    render(
      <PromotionImpactPanel
        approvedCount={0}
        acceptedClauseCount={0}
        acceptedActionCandidates={0}
        acceptedRiskCandidates={0}
      />,
    )
    expect(screen.queryByTestId('import-review-impact-attest-next')).not.toBeInTheDocument()
  })
})
