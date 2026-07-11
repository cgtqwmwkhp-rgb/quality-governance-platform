import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ImportReviewStepper, resolveActiveStep } from '../ImportReviewStepper'

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
})
