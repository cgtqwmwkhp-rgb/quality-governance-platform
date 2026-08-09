/**
 * WE-1: Doc Graph proposals are reviewable on the existing Knowledge Exceptions
 * inbox, acting through the existing Doc Graph edge routes. No twin Confirm
 * Queue route (ADR-0023), and never a copy of the edges into CEL.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import {
  buildGraphQueueHonesty,
  isBlindPendingEdge,
  isGraphQueueClosedError,
  pendingEndpointLabel,
} from '../knowledgeExceptionsGraphQueue'
import type { PendingDocumentEdgeItem } from '../../api/documentGraphClient'

const mockList = vi.fn()
const mockListPendingEdges = vi.fn()
const mockConfirmEdge = vi.fn()
const mockRejectEdge = vi.fn()
const mockToastSuccess = vi.fn()
const mockToastError = vi.fn()

const flagState: Record<string, boolean> = { document_graph: true }

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
}))

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
    confirmLink: vi.fn(),
    rejectLink: vi.fn(),
    bulkConfirm: vi.fn(),
  },
  documentGraphApi: {
    listPendingEdges: (...a: unknown[]) => mockListPendingEdges(...a),
    confirmEdge: (...a: unknown[]) => mockConfirmEdge(...a),
    rejectEdge: (...a: unknown[]) => mockRejectEdge(...a),
  },
}))

function pendingEdge(overrides: Partial<PendingDocumentEdgeItem> = {}): PendingDocumentEdgeItem {
  return {
    edge_id: 31,
    edge_type: 'implements',
    status: 'proposed',
    created_method: 'heuristic',
    is_primary_parent: true,
    impact_driving: true,
    confidence: 0.62,
    rationale: 'Cites the parent policy in section 3',
    created_at: '2026-08-01T00:00:00Z',
    src: {
      document_id: 10,
      title: 'Welding SOP',
      reference: 'PEL-HSE-01-010',
      href: '/documents/10',
      readable: true,
    },
    dst: {
      document_id: 20,
      title: 'HSE Policy',
      reference: 'PEL-HSE-01-020',
      href: '/documents/20',
      readable: true,
    },
    ...overrides,
  }
}

function pendingPage(items: PendingDocumentEdgeItem[], overrides = {}) {
  return {
    data: { items, returned: items.length, limit: 200, truncated: false, ...overrides },
  }
}

async function renderPage() {
  const KnowledgeExceptions = (await import('../KnowledgeExceptions')).default
  return render(
    <MemoryRouter>
      <KnowledgeExceptions />
    </MemoryRouter>,
  )
}

describe('knowledgeExceptionsGraphQueue helpers', () => {
  it('names an endpoint by title, then reference, and never invents a withheld one', () => {
    expect(
      pendingEndpointLabel({
        document_id: 4,
        title: 'HSE Policy',
        reference: 'PEL-1',
        href: '/documents/4',
        readable: true,
      }),
    ).toBe('HSE Policy')
    expect(
      pendingEndpointLabel({
        document_id: 4,
        title: null,
        reference: 'PEL-1',
        href: '/documents/4',
        readable: true,
      }),
    ).toBe('PEL-1')
    expect(
      pendingEndpointLabel({
        document_id: 4,
        title: null,
        reference: null,
        href: '/documents/4',
        readable: false,
      }),
    ).toBe('Document #4 — not available to you')
  })

  it('calls a proposal blind only when neither end is readable', () => {
    expect(isBlindPendingEdge(pendingEdge())).toBe(false)
    expect(
      isBlindPendingEdge(
        pendingEdge({ dst: { ...pendingEdge().dst, readable: false, title: null } }),
      ),
    ).toBe(false)
    expect(
      isBlindPendingEdge(
        pendingEdge({
          src: { ...pendingEdge().src, readable: false, title: null },
          dst: { ...pendingEdge().dst, readable: false, title: null },
        }),
      ),
    ).toBe(true)
  })

  it('says a page is a page, and says plainly when it was cut', () => {
    expect(buildGraphQueueHonesty({ returned: 1, limit: 200, truncated: false }).summary).toBe(
      '1 proposed relationship awaiting confirmation (page of up to 200 — not a global total)',
    )
    const cut = buildGraphQueueHonesty({ returned: 200, limit: 200, truncated: true })
    expect(cut.truncated).toBe(true)
    expect(cut.summary).toContain('more than 200 are pending')
  })

  it('treats a 404 as a closed flag rather than an empty queue', () => {
    expect(isGraphQueueClosedError({ response: { status: 404 } })).toBe(true)
    expect(isGraphQueueClosedError({ response: { status: 500 } })).toBe(false)
    expect(isGraphQueueClosedError(new Error('network'))).toBe(false)
  })
})

describe('KnowledgeExceptions Doc Graph queue (WE-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flagState.document_graph = true
    mockList.mockResolvedValue({ data: [] })
    mockListPendingEdges.mockResolvedValue(pendingPage([pendingEdge()]))
    mockConfirmEdge.mockResolvedValue({ data: {} })
    mockRejectEdge.mockResolvedValue({ data: {} })
  })

  it('lists proposed document↔document edges with both ends named', async () => {
    await renderPage()

    expect(await screen.findByTestId('graph-proposal-row-31')).toBeInTheDocument()
    const row = screen.getByTestId('graph-proposal-row-31')
    expect(row).toHaveTextContent('Welding SOP')
    expect(row).toHaveTextContent('HSE Policy')
    expect(row).toHaveTextContent('Implements')
    expect(row).toHaveTextContent('Primary parent')
    expect(screen.getByTestId('exceptions-graph-queue-honesty')).toHaveTextContent(
      'not a global total',
    )
  })

  it('warns that confirming an impact-driving proposal is what makes it bite', async () => {
    await renderPage()
    expect(await screen.findByTestId('graph-proposal-impact-31')).toHaveTextContent(
      /drives publish impact/i,
    )
  })

  it('confirms through the existing Doc Graph edge route and reloads the queue', async () => {
    await renderPage()

    fireEvent.click(await screen.findByTestId('graph-proposal-confirm-31'))

    await waitFor(() => {
      expect(mockConfirmEdge).toHaveBeenCalledWith(31)
    })
    expect(mockToastSuccess).toHaveBeenCalledWith('Relationship confirmed')
    await waitFor(() => {
      expect(mockListPendingEdges).toHaveBeenCalledTimes(2)
    })
  })

  it('rejects through the existing Doc Graph edge route', async () => {
    await renderPage()

    fireEvent.click(await screen.findByTestId('graph-proposal-reject-31'))

    await waitFor(() => {
      expect(mockRejectEdge).toHaveBeenCalledWith(31)
    })
    expect(mockToastSuccess).toHaveBeenCalledWith('Relationship rejected')
  })

  it('holds every other decision while one is in flight, so no click lands on a stale list', async () => {
    mockListPendingEdges.mockResolvedValue(
      pendingPage([pendingEdge(), pendingEdge({ edge_id: 32, is_primary_parent: false })]),
    )
    let releaseConfirm: (() => void) | undefined
    mockConfirmEdge.mockImplementation(
      () =>
        new Promise((resolve) => {
          releaseConfirm = () => resolve({ data: {} })
        }),
    )
    await renderPage()

    fireEvent.click(await screen.findByTestId('graph-proposal-confirm-31'))

    await waitFor(() => {
      expect(screen.getByTestId('graph-proposal-confirm-32')).toBeDisabled()
    })
    expect(screen.getByTestId('graph-proposal-reject-32')).toBeDisabled()

    fireEvent.click(screen.getByTestId('graph-proposal-confirm-32'))
    expect(mockConfirmEdge).toHaveBeenCalledTimes(1)

    releaseConfirm?.()
    await waitFor(() => {
      expect(screen.getByTestId('graph-proposal-confirm-32')).not.toBeDisabled()
    })
  })

  it('does not offer a decision on a proposal whose documents are both withheld', async () => {
    mockListPendingEdges.mockResolvedValue(
      pendingPage([
        pendingEdge({
          src: { document_id: 10, title: null, reference: null, href: '/documents/10', readable: false },
          dst: { document_id: 20, title: null, reference: null, href: '/documents/20', readable: false },
        }),
      ]),
    )
    await renderPage()

    expect(await screen.findByTestId('graph-proposal-blind-31')).toBeInTheDocument()
    expect(screen.queryByTestId('graph-proposal-confirm-31')).not.toBeInTheDocument()
    expect(screen.queryByTestId('graph-proposal-reject-31')).not.toBeInTheDocument()
  })

  it('says the page was cut instead of implying a total', async () => {
    mockListPendingEdges.mockResolvedValue(
      pendingPage([pendingEdge()], { returned: 200, limit: 200, truncated: true }),
    )
    await renderPage()

    expect(await screen.findByTestId('exceptions-graph-queue-honesty')).toHaveTextContent(
      /more than 200 are pending/,
    )
  })

  it('distinguishes a closed Doc Graph flag from an empty queue', async () => {
    mockListPendingEdges.mockRejectedValue({ response: { status: 404 } })
    await renderPage()

    expect(await screen.findByTestId('exceptions-graph-queue-closed')).toHaveTextContent(
      /not a statement that none are pending/i,
    )
    expect(screen.queryByTestId('exceptions-graph-queue-empty')).not.toBeInTheDocument()
  })

  it('never reports zero when the queue read failed', async () => {
    mockListPendingEdges.mockRejectedValue(new Error('gateway timeout'))
    await renderPage()

    expect(await screen.findByTestId('exceptions-graph-queue-error')).toHaveTextContent(
      /not a zero/i,
    )
    expect(screen.queryByTestId('exceptions-graph-queue-empty')).not.toBeInTheDocument()
  })

  it('says the queue is clear only when the server said so', async () => {
    mockListPendingEdges.mockResolvedValue(pendingPage([]))
    await renderPage()

    expect(await screen.findByTestId('exceptions-graph-queue-empty')).toBeInTheDocument()
  })

  it('shows nothing and asks the API for nothing while Doc Graph is closed', async () => {
    flagState.document_graph = false
    await renderPage()

    await waitFor(() => {
      expect(mockList).toHaveBeenCalled()
    })
    expect(screen.queryByTestId('exceptions-graph-queue')).not.toBeInTheDocument()
    expect(mockListPendingEdges).not.toHaveBeenCalled()
  })
})
