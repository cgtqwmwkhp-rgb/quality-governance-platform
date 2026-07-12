import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  ImportReviewStepper,
  resolveActiveStep,
  resolveNextStepCopy,
} from '../ImportReviewStepper'

describe('ImportReviewStepper', () => {
  it('resolves upload when no job', () => {
    expect(resolveActiveStep({ hasJob: false })).toBe('upload')
  })

  it('resolves processing when running', () => {
    expect(resolveActiveStep({ hasJob: true, isProcessing: true })).toBe('processing')
  })

  it('resolves promote when promoteable drafts exist', () => {
    expect(resolveActiveStep({ hasJob: true, promoteableCount: 2 })).toBe('promote')
  })

  it('renders four CUJ steps', () => {
    render(<ImportReviewStepper hasJob jobStatus="ready" promoteableCount={0} />)
    expect(screen.getByLabelText('Import review steps')).toBeInTheDocument()
    expect(screen.getByText('Upload')).toBeInTheDocument()
    expect(screen.getByText('Processing')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(screen.getByText('Promote')).toBeInTheDocument()
  })

  it('shows next-step copy for the review step', () => {
    render(<ImportReviewStepper hasJob jobStatus="ready" promoteableCount={0} />)
    expect(screen.getByTestId('import-review-stepper-next')).toHaveTextContent(
      'Next: Promote — accept drafts, then promote into governance outcomes.',
    )
  })

  it('shows processing next-step copy while extraction runs', () => {
    render(<ImportReviewStepper hasJob isProcessing jobStatus="processing" />)
    expect(screen.getByTestId('import-review-stepper-next')).toHaveTextContent(
      'Next: Review — check draft findings when extraction finishes.',
    )
  })

  it('shows completion copy after promotion', () => {
    expect(resolveNextStepCopy('promote', { jobStatus: 'completed' })).toBe(
      'Import complete — accepted drafts have been promoted.',
    )
    render(<ImportReviewStepper hasJob jobStatus="completed" promoteableCount={0} />)
    expect(screen.getByTestId('import-review-stepper-next')).toHaveTextContent(
      'Import complete — accepted drafts have been promoted.',
    )
  })

  it('shows ≤2-click attest next-step when promoteable drafts are ready', () => {
    expect(
      resolveNextStepCopy('promote', { jobStatus: 'review_required', promoteableCount: 3 }),
    ).toBe('Next: Promote Now, then Confirm — two clicks to attest accepted drafts.')
    render(
      <ImportReviewStepper hasJob jobStatus="review_required" promoteableCount={3} />,
    )
    expect(screen.getByTestId('import-review-stepper-next')).toHaveTextContent(
      'Next: Promote Now, then Confirm — two clicks to attest accepted drafts.',
    )
  })
})
