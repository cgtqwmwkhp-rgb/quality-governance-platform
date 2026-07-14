import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const mockList = vi.fn()
const mockTrail = vi.fn()
const mockAssess = vi.fn()
const mockReject = vi.fn()
const mockConfirm = vi.fn()
const mockToastError = vi.fn()
const mockToastSuccess = vi.fn()

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
    success: (...args: unknown[]) => mockToastSuccess(...args),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('../../api/client', () => ({
  getApiErrorMessage: (e: unknown, fallback?: string) =>
    e instanceof Error ? e.message : fallback || 'fail',
  knowledgeBankApi: {
    listEntityAssessment: (...a: unknown[]) => mockList(...a),
    listEntityAssessmentTrail: (...a: unknown[]) => mockTrail(...a),
    assessEntity: (...a: unknown[]) => mockAssess(...a),
    rejectLink: (...a: unknown[]) => mockReject(...a),
    confirmLink: (...a: unknown[]) => mockConfirm(...a),
  },
}))

describe('StandardsAssessmentPanel closed-loop deeplink', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: [] })
    mockTrail.mockResolvedValue({ data: { items: [] } })
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

describe('StandardsAssessmentPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: [] })
    mockTrail.mockResolvedValue({ data: { items: [] } })
    mockAssess.mockResolvedValue({
      data: {
        links_created: 1,
        links: [],
        related_documents: [],
        assessment_statement: 'Mapped',
        signal_type: 'gap',
      },
    })
  })

  it('shows clear Map to ISO / UVDB / Planet Mark CTA', async () => {
    const { StandardsAssessmentPanel } = await import('../StandardsAssessmentPanel')
    render(
      <MemoryRouter>
        <StandardsAssessmentPanel entityType="incident" entityId={7} />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('standards-map-cta')).toHaveTextContent(
      /Map to ISO \/ UVDB \/ Planet Mark/i,
    )
    fireEvent.click(screen.getByTestId('standards-map-cta'))
    await waitFor(() => {
      expect(mockAssess).toHaveBeenCalledWith('incident', 7)
    })
  })

  it('requires reject rationale before calling API', async () => {
    mockList.mockResolvedValue({
      data: [
        {
          id: 3,
          entity_type: 'incident',
          entity_id: '7',
          clause_id: 'ISO9001:8.5',
          linked_by: 'ai',
          confidence: 0.5,
          status: 'proposed',
          scheme: 'iso9001',
          auto_applied: false,
          rationale: 'possible gap',
          title: 'Gap',
          notes: null,
          signal_type: 'gap',
          created_at: '2026-07-13T00:00:00Z',
          created_by_email: null,
        },
      ],
    })
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('')
    const { StandardsAssessmentPanel } = await import('../StandardsAssessmentPanel')
    render(
      <MemoryRouter>
        <StandardsAssessmentPanel entityType="incident" entityId={7} />
      </MemoryRouter>,
    )
    expect(await screen.findByText('ISO9001:8.5')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Reject/i }))
    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(expect.stringMatching(/rationale/i))
    })
    expect(mockReject).not.toHaveBeenCalled()
    prompt.mockRestore()
  })
})

describe('StandardsAssessmentPanel audit trail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: [] })
    mockTrail.mockResolvedValue({
      data: {
        entity_type: 'incident',
        entity_id: '1',
        items: [
          {
            id: 1,
            action: 'evidence_confirm',
            confidence: null,
            auto_applied: false,
            payload: { actor_email: 'a@b.co', clause_id: '7.5' },
            created_at: '2026-07-13T10:00:00Z',
          },
        ],
      },
    })
  })

  it('toggles audit trail panel with persisted confirm entries', async () => {
    const user = userEvent.setup()
    const { StandardsAssessmentPanel } = await import('../StandardsAssessmentPanel')
    render(
      <MemoryRouter>
        <StandardsAssessmentPanel entityType="incident" entityId={1} />
      </MemoryRouter>,
    )

    await waitFor(() => expect(mockTrail).toHaveBeenCalled())
    await user.click(screen.getByTestId('assessment-trail-toggle'))
    expect(await screen.findByTestId('assessment-trail-panel')).toHaveTextContent('Confirmed')
    expect(screen.getByTestId('assessment-trail-panel')).toHaveTextContent('7.5')
  })
})
