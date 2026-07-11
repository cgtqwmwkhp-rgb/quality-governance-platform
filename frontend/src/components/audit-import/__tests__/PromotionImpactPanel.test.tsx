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
})
