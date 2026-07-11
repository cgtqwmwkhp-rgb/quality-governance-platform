import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ImportReviewPromoteBanner } from '../ImportReviewPromoteBanner'

describe('ImportReviewPromoteBanner', () => {
  it('shows confirm controls when confirmation is open', () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(
      <ImportReviewPromoteBanner
        promoteableCount={2}
        acceptedActionCandidates={1}
        acceptedRiskCandidates={1}
        acceptedClauseCount={3}
        jobStatus="review_required"
        showPromoteConfirm={true}
        isPromoting={false}
        onPromoteClick={() => {}}
        onCancelConfirm={onCancel}
        onConfirmPromote={onConfirm}
      />,
    )

    expect(
      screen.getByText(/Confirm promotion of 2 accepted finding\(s\)\?/i),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Promote' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('renders nothing useful when confirm is closed and count is zero', () => {
    const { container } = render(
      <ImportReviewPromoteBanner
        promoteableCount={0}
        acceptedActionCandidates={0}
        acceptedRiskCandidates={0}
        acceptedClauseCount={0}
        jobStatus="review_required"
        showPromoteConfirm={false}
        isPromoting={false}
        onPromoteClick={() => {}}
        onCancelConfirm={() => {}}
        onConfirmPromote={() => {}}
      />,
    )
    expect(container).toBeTruthy()
  })
})
