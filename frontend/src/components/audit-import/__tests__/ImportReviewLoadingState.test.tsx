import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ImportReviewLoadingState } from '../ImportReviewLoadingState'

describe('ImportReviewLoadingState', () => {
  it('renders Import Review chrome while loading', () => {
    render(
      <ImportReviewLoadingState
        specialistHomeLabel="Open specialist home"
        onOpenSpecialistHome={vi.fn()}
      />,
    )
    expect(screen.getByRole('heading', { name: /external audit review/i })).toBeInTheDocument()
  })
})
