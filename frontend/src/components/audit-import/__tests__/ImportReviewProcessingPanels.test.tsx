import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ImportReviewProcessingPanels } from '../ImportReviewProcessingPanels'

describe('ImportReviewProcessingPanels', () => {
  it('shows processing status when isProcessing', () => {
    render(
      <ImportReviewProcessingPanels
        job={null}
        isProcessing={true}
        isQueueing={false}
        onRetryQueue={() => {}}
      />,
    )
    expect(screen.getByText(/Processing import/i)).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows queue retry when pending and not processing', () => {
    const onRetry = vi.fn()
    render(
      <ImportReviewProcessingPanels
        job={{ id: 9, status: 'queued', error_code: null, error_detail: null, processing_warnings_json: [] } as never}
        isProcessing={false}
        isQueueing={false}
        onRetryQueue={onRetry}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Retry Queue/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
