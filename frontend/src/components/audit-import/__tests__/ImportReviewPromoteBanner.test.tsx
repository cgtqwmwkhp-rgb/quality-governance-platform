import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ImportReviewPromoteBanner } from '../ImportReviewPromoteBanner'

const baseProps = {
  promoteableCount: 2,
  acceptedActionCandidates: 1,
  acceptedRiskCandidates: 1,
  acceptedClauseCount: 3,
  jobStatus: 'review_required' as string | null,
  showPromoteConfirm: false,
  isPromoting: false,
  onPromoteClick: () => {},
  onCancelConfirm: () => {},
  onConfirmPromote: () => {},
}

describe('ImportReviewPromoteBanner', () => {
  it('shows ready CTA with two-click attest next-step copy', () => {
    const onPromote = vi.fn()
    render(
      <ImportReviewPromoteBanner {...baseProps} onPromoteClick={onPromote} />,
    )

    expect(screen.getByTestId('import-review-promote-ready')).toBeInTheDocument()
    expect(
      screen.getByText(/Next: Promote Now, then Confirm — two clicks to attest/i),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Promote Now/i }))
    expect(onPromote).toHaveBeenCalledTimes(1)
  })

  it('shows attest confirm controls when confirmation is open', () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(
      <ImportReviewPromoteBanner
        {...baseProps}
        showPromoteConfirm={true}
        onCancelConfirm={onCancel}
        onConfirmPromote={onConfirm}
      />,
    )

    expect(screen.getByTestId('import-review-promote-attest')).toBeInTheDocument()
    expect(
      screen.getByText(/Attest promotion of 2 accepted finding\(s\)\?/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/Final confirm \(click 2 of 2\)/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Promote' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('disables attest controls and shows Promoting… while busy', () => {
    render(
      <ImportReviewPromoteBanner
        {...baseProps}
        showPromoteConfirm={true}
        isPromoting={true}
      />,
    )

    expect(screen.getByRole('button', { name: /Promoting/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled()
  })

  it('renders nothing useful when confirm is closed and count is zero', () => {
    const { container } = render(
      <ImportReviewPromoteBanner
        {...baseProps}
        promoteableCount={0}
        acceptedActionCandidates={0}
        acceptedRiskCandidates={0}
        acceptedClauseCount={0}
      />,
    )
    expect(container).toBeTruthy()
    expect(screen.queryByTestId('import-review-promote-ready')).not.toBeInTheDocument()
  })
})
