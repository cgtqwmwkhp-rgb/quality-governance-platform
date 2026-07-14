import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mockList = vi.fn()
const mockAssess = vi.fn()
const mockReject = vi.fn()
const mockConfirm = vi.fn()

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('../../api/client', () => ({
  getApiErrorMessage: (e: unknown) => (e instanceof Error ? e.message : 'fail'),
  knowledgeBankApi: {
    listEntityAssessment: (...a: unknown[]) => mockList(...a),
    assessEntity: (...a: unknown[]) => mockAssess(...a),
    rejectLink: (...a: unknown[]) => mockReject(...a),
    confirmLink: (...a: unknown[]) => mockConfirm(...a),
  },
}))

describe('StandardsAssessmentPanel closed-loop deeplink', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: [] })
  })

  it('links to Knowledge Exceptions with entity_type filter and returnTo', async () => {
    const { StandardsAssessmentPanel } = await import('../StandardsAssessmentPanel')
    render(
      <MemoryRouter>
        <StandardsAssessmentPanel entityType="near_miss" entityId={12} />
      </MemoryRouter>,
    )

    const link = await screen.findByTestId('standards-exceptions-deeplink')
    expect(link).toHaveAttribute(
      'href',
      expect.stringContaining('/knowledge-exceptions?'),
    )
    expect(link.getAttribute('href')).toContain('entity_type=near_miss')
    expect(link.getAttribute('href')).toContain(encodeURIComponent('/near-misses/12'))
    expect(screen.getByTestId('standards-exceptions-hint')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith('near_miss', 12)
    })
  })
})
