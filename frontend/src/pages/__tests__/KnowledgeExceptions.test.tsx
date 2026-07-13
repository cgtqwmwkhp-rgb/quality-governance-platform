import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import {
  exceptionEntityHref,
  isSafeReturnTo,
  knowledgeExceptionsClosedLoopHref,
  parseEntityTypeFilter,
} from '../../helpers/knowledgeExceptionsLinks'

const mockList = vi.fn()
const mockConfirm = vi.fn()
const mockReject = vi.fn()
const mockBulkConfirm = vi.fn()
const mockToastSuccess = vi.fn()
const mockToastError = vi.fn()

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
    success: (...args: unknown[]) => mockToastSuccess(...args),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('../../api/client', () => ({
  getApiErrorMessage: (e: unknown) => (e instanceof Error ? e.message : 'fail'),
  knowledgeBankApi: {
    listExceptions: (...a: unknown[]) => mockList(...a),
    confirmLink: (...a: unknown[]) => mockConfirm(...a),
    rejectLink: (...a: unknown[]) => mockReject(...a),
    bulkConfirm: (...a: unknown[]) => mockBulkConfirm(...a),
  },
}))

describe('knowledgeExceptionsLinks', () => {
  it('deep-links documents to Standards & Evidence tab', () => {
    expect(exceptionEntityHref('document', '42')).toBe('/documents/42?tab=evidence')
  })

  it('maps operational entity types to detail routes', () => {
    expect(exceptionEntityHref('incident', '7')).toBe('/incidents/7')
    expect(exceptionEntityHref('complaint', '3')).toBe('/complaints/3')
    expect(exceptionEntityHref('near_miss', '9')).toBe('/near-misses/9')
    expect(exceptionEntityHref('rta', '5')).toBe('/rtas/5')
    expect(exceptionEntityHref('audit_finding', '11')).toBe(
      '/audits?view=findings&findingId=11',
    )
  })

  it('returns null for unknown types or empty id', () => {
    expect(exceptionEntityHref('policy', '1')).toBeNull()
    expect(exceptionEntityHref('incident', '')).toBeNull()
  })

  it('builds closed-loop Exceptions href with entity_type + returnTo', () => {
    const href = knowledgeExceptionsClosedLoopHref('incident', 7)
    expect(href).toContain('/knowledge-exceptions?')
    expect(href).toContain('entity_type=incident')
    expect(href).toContain(encodeURIComponent('/incidents/7'))
  })

  it('parses entity_type filter safely', () => {
    expect(parseEntityTypeFilter('near_miss')).toBe('near_miss')
    expect(parseEntityTypeFilter('nope')).toBe('all')
    expect(parseEntityTypeFilter(null)).toBe('all')
  })

  it('rejects unsafe returnTo targets', () => {
    expect(isSafeReturnTo('/incidents/1')).toBe(true)
    expect(isSafeReturnTo('//evil.com')).toBe(false)
    expect(isSafeReturnTo('https://evil.com')).toBe(false)
    expect(isSafeReturnTo(null)).toBe(false)
  })
})

describe('KnowledgeExceptions closed loop', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: [
        {
          id: 9,
          entity_type: 'incident',
          entity_id: '7',
          clause_id: 'ISO9001:8.5',
          linked_by: 'ai',
          confidence: 0.7,
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
    mockConfirm.mockResolvedValue({ data: {} })
    mockReject.mockResolvedValue({ data: {} })
  })

  it('hydrates entity_type filter from URL and shows return banner', async () => {
    const { default: KnowledgeExceptions } = await import('../KnowledgeExceptions')
    render(
      <MemoryRouter
        initialEntries={[
          '/knowledge-exceptions?entity_type=incident&returnTo=%2Fincidents%2F7',
        ]}
      >
        <Routes>
          <Route path="/knowledge-exceptions" element={<KnowledgeExceptions />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith({ status: undefined, entityType: 'incident', signalType: undefined })
    })
    expect(screen.getByTestId('exceptions-return-to-case')).toBeInTheDocument()
    expect(screen.getByTestId('exceptions-return-to-case-link')).toHaveAttribute(
      'href',
      '/incidents/7',
    )
    expect(screen.getByTestId('exceptions-filter-honesty')).toHaveTextContent('entity=incident')
  })

  it('confirm returns to case when returnTo is present', async () => {
    const { default: KnowledgeExceptions } = await import('../KnowledgeExceptions')
    render(
      <MemoryRouter
        initialEntries={[
          '/knowledge-exceptions?entity_type=incident&returnTo=%2Fincidents%2F7',
        ]}
      >
        <Routes>
          <Route path="/knowledge-exceptions" element={<KnowledgeExceptions />} />
          <Route path="/incidents/:id" element={<div data-testid="case-home">Case</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('ISO9001:8.5')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('exception-confirm-9'))
    await waitFor(() => {
      expect(mockConfirm).toHaveBeenCalledWith(9)
    })
    expect(await screen.findByTestId('case-home')).toBeInTheDocument()
  })
})

describe('KnowledgeExceptions server signal filter honesty', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: [] })
  })

  it('loads exceptions and shows map CTA + server-filter honesty copy', async () => {
    const KnowledgeExceptions = (await import('../KnowledgeExceptions')).default
    render(
      <MemoryRouter>
        <KnowledgeExceptions />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('exceptions-map-cta-banner')).toHaveTextContent(
      /Map inputs/i,
    )
    expect(screen.getByTestId('exceptions-filter-honesty')).toHaveTextContent(/server filters/i)
    await waitFor(() => {
      expect(mockList).toHaveBeenCalled()
    })
  })
})


describe('exceptions inbox URL sync', () => {
  it('encodes status + entity_type + signal_type', async () => {
    const { buildExceptionsInboxSearch } = await import('../exceptionsInboxFilters')
    expect(
      buildExceptionsInboxSearch({
        status: 'needs_review',
        entityType: 'near_miss',
        signalType: 'nonconformity',
      }),
    ).toBe('status=needs_review&entity_type=near_miss&signal_type=nonconformity')
  })
})
