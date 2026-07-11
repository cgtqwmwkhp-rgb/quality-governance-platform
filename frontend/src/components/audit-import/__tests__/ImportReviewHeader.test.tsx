import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ImportReviewHeader } from '../ImportReviewHeader'

describe('ImportReviewHeader', () => {
  it('renders title and invokes bulk approve / promote actions', () => {
    const onBulkApprove = vi.fn()
    const onPromoteClick = vi.fn()
    const onOpenSpecialistHome = vi.fn()

    render(
      <ImportReviewHeader
        pendingDraftCount={3}
        promoteableCount={2}
        isBulkReviewing={false}
        isPromoting={false}
        hasJob={true}
        jobStatus="review_required"
        specialistHomeLabel="Open Achilles / UVDB"
        onBulkApprove={onBulkApprove}
        onOpenSpecialistHome={onOpenSpecialistHome}
        onPromoteClick={onPromoteClick}
      />,
    )

    expect(screen.getByRole('heading', { name: 'External Audit Review' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Approve All Pending/i }))
    fireEvent.click(screen.getByRole('button', { name: /Promote Accepted Drafts/i }))
    fireEvent.click(screen.getByRole('button', { name: /Open Achilles \/ UVDB/i }))
    expect(onBulkApprove).toHaveBeenCalledTimes(1)
    expect(onPromoteClick).toHaveBeenCalledTimes(1)
    expect(onOpenSpecialistHome).toHaveBeenCalledTimes(1)
  })

  it('disables promote when job is already promoting', () => {
    render(
      <ImportReviewHeader
        pendingDraftCount={1}
        promoteableCount={1}
        isBulkReviewing={false}
        isPromoting={false}
        hasJob={true}
        jobStatus="promoting"
        specialistHomeLabel="Open specialist home"
        onBulkApprove={() => {}}
        onOpenSpecialistHome={() => {}}
        onPromoteClick={() => {}}
      />,
    )

    expect(screen.getByRole('button', { name: /Promote Accepted Drafts/i })).toBeDisabled()
  })
})
