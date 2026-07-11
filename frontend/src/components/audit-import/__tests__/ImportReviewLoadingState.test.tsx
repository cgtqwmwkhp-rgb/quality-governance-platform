import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ImportReviewLoadingState } from '../ImportReviewLoadingState'

describe('ImportReviewLoadingState', () => {
  it('renders Import Review chrome and loading skeleton', () => {
    render(
      <ImportReviewLoadingState
        specialistHomeLabel="Open Achilles / UVDB"
        onOpenSpecialistHome={() => {}}
      />,
    )

    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Promote Accepted Drafts' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Approve All Pending' })).toBeDisabled()
  })

  it('keeps specialist home control visible but disabled until job loads', () => {
    render(
      <ImportReviewLoadingState
        specialistHomeLabel="Open Achilles / UVDB"
        onOpenSpecialistHome={() => {}}
      />,
    )

    expect(screen.getByRole('button', { name: 'Open Achilles / UVDB' })).toBeDisabled()
  })
})
