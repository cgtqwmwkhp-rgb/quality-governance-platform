import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ImportReviewNotices } from '../ImportReviewNotices'

describe('ImportReviewNotices', () => {
  it('shows success banner and dismisses it in pre-proof section', () => {
    const onDismiss = vi.fn()
    render(
      <ImportReviewNotices
        section="pre-proof"
        successMessage="Approved 2 pending finding(s)."
        onDismissSuccess={onDismiss}
        reconciliationNotice={null}
        error={null}
        promotionFailedDrafts={null}
        onRetryLoad={() => {}}
        queueNotice={null}
        job={null}
        isQueueing={false}
        onRetryQueue={() => {}}
      />,
    )

    expect(screen.getByText(/Approved 2 pending finding\(s\)/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('shows error and retry in post-proof section', () => {
    const onRetry = vi.fn()
    render(
      <ImportReviewNotices
        section="post-proof"
        successMessage={null}
        onDismissSuccess={() => {}}
        reconciliationNotice={null}
        error="Failed to load drafts"
        promotionFailedDrafts={null}
        onRetryLoad={onRetry}
        queueNotice={null}
        job={null}
        isQueueing={false}
        onRetryQueue={() => {}}
      />,
    )

    expect(screen.getByText('Failed to load drafts')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
