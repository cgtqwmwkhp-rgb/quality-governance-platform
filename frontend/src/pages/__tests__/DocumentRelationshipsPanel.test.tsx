import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { DocumentEdge } from '../../api/documentGraphClient'
import { DocumentRelationshipsPanel } from '../DocumentRelationshipsPanel'

const apiGet = vi.fn()
const graph = {
  createEdge: vi.fn(),
  confirmEdge: vi.fn(),
  rejectEdge: vi.fn(),
  deleteEdge: vi.fn(),
  confirmEdges: vi.fn(),
  proposeHeuristics: vi.fn(),
  getCitationStaleness: vi.fn(),
}

vi.mock('../../api/client', () => ({
  default: { get: (...args: unknown[]) => apiGet(...args) },
  documentGraphApi: {
    createEdge: (...args: unknown[]) => graph.createEdge(...args),
    confirmEdge: (...args: unknown[]) => graph.confirmEdge(...args),
    rejectEdge: (...args: unknown[]) => graph.rejectEdge(...args),
    deleteEdge: (...args: unknown[]) => graph.deleteEdge(...args),
    confirmEdges: (...args: unknown[]) => graph.confirmEdges(...args),
    proposeHeuristics: (...args: unknown[]) => graph.proposeHeuristics(...args),
    getCitationStaleness: (...args: unknown[]) => graph.getCitationStaleness(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => key === 'document_graph_heuristic_propose',
}))

function edge(overrides: Partial<DocumentEdge> & { id: number }): DocumentEdge {
  return {
    tenant_id: 1,
    src_document_id: 10,
    dst_document_id: 20,
    edge_type: 'implements',
    is_primary_parent: false,
    status: 'confirmed',
    created_method: 'manual',
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

function renderPanel(edges: DocumentEdge[], onChanged = vi.fn()) {
  return {
    onChanged,
    ...render(
      <MemoryRouter>
        <DocumentRelationshipsPanel
          documentId={10}
          documentTitle="Incident Management Policy"
          edges={edges}
          loading={false}
          error={null}
          onChanged={onChanged}
        />
      </MemoryRouter>,
    ),
  }
}

describe('DocumentRelationshipsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiGet.mockResolvedValue({ data: { id: 20, title: 'Incident Reporting SOP' } })
    graph.getCitationStaleness.mockResolvedValue({ data: { edge_id: 1, status: 'unchanged' } })
    graph.proposeHeuristics.mockResolvedValue({
      data: { created: [], created_count: 0, skipped_existing: 0, skipped_unresolved: 0, sources: {} },
    })
  })

  it('resolves counterpart titles and shows the confirmed list', async () => {
    renderPanel([edge({ id: 1 })])

    expect(await screen.findByText('Incident Reporting SOP')).toBeInTheDocument()
    expect(apiGet).toHaveBeenCalledWith('/api/v1/documents/20')
    expect(screen.getByTestId('relationships-confirmed-list')).toBeInTheDocument()
    expect(screen.getByTestId('relationships-breakdown')).toHaveTextContent(
      '1 from this document',
    )
  })

  it('offers suggest relationships when heuristic propose flag is on', async () => {
    graph.proposeHeuristics.mockResolvedValue({
      data: {
        created: [edge({ id: 9, status: 'proposed', created_method: 'heuristic', edge_type: 'related_to' })],
        created_count: 1,
        skipped_existing: 0,
        skipped_unresolved: 0,
        sources: { category_pel_siblings: 1 },
      },
    })
    const { onChanged } = renderPanel([])

    fireEvent.click(screen.getByTestId('relationships-propose-heuristics'))
    await waitFor(() => expect(graph.proposeHeuristics).toHaveBeenCalledWith(10))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('shows citation staleness for references edges with quote_hash', async () => {
    graph.getCitationStaleness.mockResolvedValue({
      data: { edge_id: 7, status: 'moved', quote_hash: 'abc' },
    })
    renderPanel([
      edge({
        id: 7,
        edge_type: 'references',
        quote_hash: 'abc',
        citation_text: 'DOC-2026-0042',
      }),
    ])

    expect(await screen.findByTestId('relationship-citation-staleness-7')).toHaveTextContent(
      'Citation moved',
    )
    expect(graph.getCitationStaleness).toHaveBeenCalledWith(7)
  })

  it('says so plainly when a counterpart is not readable instead of guessing a title', async () => {
    apiGet.mockRejectedValue(new Error('Forbidden'))
    renderPanel([edge({ id: 1, dst_pel_doc_ref: 'PEL-POL-014' })])

    expect(await screen.findByText('PEL-POL-014 — not available to you')).toBeInTheDocument()
  })

  it('offers an honest empty state when nothing is linked', () => {
    renderPanel([])
    expect(screen.getByText('No relationships recorded')).toBeInTheDocument()
    expect(screen.queryByTestId('relationships-confirm-queue')).not.toBeInTheDocument()
  })

  it('confirms a proposed edge and refreshes', async () => {
    graph.confirmEdge.mockResolvedValue({ data: edge({ id: 1, status: 'confirmed' }) })
    const { onChanged } = renderPanel([edge({ id: 1, status: 'proposed' })])

    fireEvent.click(screen.getByTestId('relationship-confirm-1'))

    await waitFor(() => expect(graph.confirmEdge).toHaveBeenCalledWith(1))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('rejects a proposed edge', async () => {
    graph.rejectEdge.mockResolvedValue({ data: edge({ id: 1, status: 'rejected' }) })
    renderPanel([edge({ id: 1, status: 'needs_review' })])

    fireEvent.click(screen.getByTestId('relationship-reject-1'))
    await waitFor(() => expect(graph.rejectEdge).toHaveBeenCalledWith(1))
  })

  it('bulk confirms the whole queue after select all', async () => {
    graph.confirmEdges.mockResolvedValue({ confirmed: [], failed: [] })
    renderPanel([
      edge({ id: 1, status: 'proposed', dst_document_id: 20 }),
      edge({ id: 2, status: 'proposed', dst_document_id: 21 }),
    ])

    fireEvent.click(screen.getByTestId('relationships-select-all'))
    fireEvent.click(screen.getByTestId('relationships-bulk-confirm'))

    await waitFor(() => expect(graph.confirmEdges).toHaveBeenCalledWith([1, 2]))
  })

  it('keeps bulk confirm disabled until something is selected', async () => {
    renderPanel([edge({ id: 1, status: 'proposed' })])
    await screen.findByText('Incident Reporting SOP')
    expect(screen.getByTestId('relationships-bulk-confirm')).toBeDisabled()
  })

  it('records a hand-authored implements edge as confirmed, with the open document as source', async () => {
    graph.createEdge.mockResolvedValue({ data: edge({ id: 5 }) })
    apiGet.mockImplementation((url: string) => {
      if (url === '/api/v1/documents/') {
        return Promise.resolve({
          data: { items: [{ id: 33, title: 'HSEQ Policy', reference_number: 'DOC-2026-0033' }] },
        })
      }
      return Promise.resolve({ data: { id: 20, title: 'Incident Reporting SOP' } })
    })

    renderPanel([])

    fireEvent.change(screen.getByTestId('relationships-search'), {
      target: { value: 'HSEQ' },
    })
    const result = await screen.findByTestId('relationships-search-result-33')
    fireEvent.click(result)
    fireEvent.change(screen.getByTestId('relationships-rationale'), {
      target: { value: 'Carries out the HSEQ policy' },
    })
    fireEvent.click(screen.getByTestId('relationships-submit'))

    await waitFor(() =>
      expect(graph.createEdge).toHaveBeenCalledWith({
        src_document_id: 10,
        dst_document_id: 33,
        edge_type: 'implements',
        is_primary_parent: true,
        status: 'confirmed',
        created_method: 'manual',
        rationale: 'Carries out the HSEQ policy',
      }),
    )
  })

  it('blocks a duplicate relationship before it reaches the API', async () => {
    apiGet.mockImplementation((url: string) => {
      if (url === '/api/v1/documents/') {
        return Promise.resolve({ data: { items: [{ id: 20, title: 'Incident Reporting SOP' }] } })
      }
      return Promise.resolve({ data: { id: 20, title: 'Incident Reporting SOP' } })
    })

    renderPanel([edge({ id: 1, src_document_id: 10, dst_document_id: 20 })])

    fireEvent.change(screen.getByTestId('relationships-search'), { target: { value: 'Incident' } })
    fireEvent.click(await screen.findByTestId('relationships-search-result-20'))

    expect(await screen.findByTestId('relationships-duplicate-warning')).toHaveTextContent(
      'already exists',
    )
    expect(screen.getByTestId('relationships-submit')).toBeDisabled()
    expect(graph.createEdge).not.toHaveBeenCalled()
  })

  it('explains that a rejected pair must be unlinked before it can be proposed again', async () => {
    apiGet.mockImplementation((url: string) => {
      if (url === '/api/v1/documents/') {
        return Promise.resolve({ data: { items: [{ id: 20, title: 'Incident Reporting SOP' }] } })
      }
      return Promise.resolve({ data: { id: 20, title: 'Incident Reporting SOP' } })
    })

    renderPanel([edge({ id: 1, src_document_id: 10, dst_document_id: 20, status: 'rejected' })])

    fireEvent.change(screen.getByTestId('relationships-search'), { target: { value: 'Incident' } })
    fireEvent.click(await screen.findByTestId('relationships-search-result-20'))

    expect(await screen.findByTestId('relationships-duplicate-warning')).toHaveTextContent(
      'Remove the rejected entry',
    )
    expect(screen.getByTestId('relationships-rejected-list')).toBeInTheDocument()
  })

  it('drops the primary-parent flag when the relationship is not implements', async () => {
    graph.createEdge.mockResolvedValue({ data: edge({ id: 6 }) })
    apiGet.mockImplementation((url: string) => {
      if (url === '/api/v1/documents/') {
        return Promise.resolve({ data: { items: [{ id: 44, title: 'Incident Report Form' }] } })
      }
      return Promise.resolve({ data: { id: 20, title: 'Incident Reporting SOP' } })
    })

    renderPanel([])

    fireEvent.change(screen.getByTestId('relationships-search'), { target: { value: 'Form' } })
    fireEvent.click(await screen.findByTestId('relationships-search-result-44'))
    fireEvent.change(screen.getByTestId('relationships-type'), {
      target: { value: 'requires_record' },
    })
    expect(screen.queryByTestId('relationships-primary-parent')).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('relationships-submit'))

    await waitFor(() =>
      expect(graph.createEdge).toHaveBeenCalledWith(
        expect.objectContaining({
          edge_type: 'requires_record',
          is_primary_parent: false,
        }),
      ),
    )
  })

  it('swaps the endpoints when the operator inverts the direction', async () => {
    graph.createEdge.mockResolvedValue({ data: edge({ id: 7 }) })
    apiGet.mockImplementation((url: string) => {
      if (url === '/api/v1/documents/') {
        return Promise.resolve({ data: { items: [{ id: 55, title: 'Site RAMS' }] } })
      }
      return Promise.resolve({ data: { id: 20, title: 'Incident Reporting SOP' } })
    })

    renderPanel([])

    fireEvent.change(screen.getByTestId('relationships-search'), { target: { value: 'RAMS' } })
    fireEvent.click(await screen.findByTestId('relationships-search-result-55'))
    fireEvent.change(screen.getByTestId('relationships-direction'), {
      target: { value: 'inbound' },
    })
    fireEvent.click(screen.getByTestId('relationships-submit'))

    await waitFor(() =>
      expect(graph.createEdge).toHaveBeenCalledWith(
        expect.objectContaining({ src_document_id: 55, dst_document_id: 10 }),
      ),
    )
  })

  it('hides the direction picker for peer types and flags conflicts as human-only', async () => {
    renderPanel([])

    fireEvent.change(screen.getByTestId('relationships-type'), {
      target: { value: 'conflicts_with' },
    })

    expect(screen.queryByTestId('relationships-direction')).not.toBeInTheDocument()
    expect(screen.getByTestId('relationships-type-helper')).toHaveTextContent(
      'Only a person may record a conflict',
    )
  })

  it('surfaces an active conflict in the summary strip', async () => {
    renderPanel([edge({ id: 1, edge_type: 'conflicts_with', dst_document_id: 20 })])
    await screen.findByText('Incident Reporting SOP')
    expect(screen.getByTestId('relationships-conflict-count')).toHaveTextContent('1 conflict')
  })

  it('never describes Doc Graph edges as the golden thread', async () => {
    const { container } = renderPanel([edge({ id: 1, status: 'proposed' })])
    await screen.findByText('Incident Reporting SOP')
    expect(container.textContent?.toLowerCase()).not.toContain('golden thread')
  })

  it('unlinks a confirmed relationship so the pair can be re-authored', async () => {
    graph.deleteEdge.mockResolvedValue({ data: edge({ id: 1 }) })
    const { onChanged } = renderPanel([edge({ id: 1 })])
    await screen.findByText('Incident Reporting SOP')

    fireEvent.click(screen.getByTestId('relationship-unlink-1'))

    await waitFor(() => expect(graph.deleteEdge).toHaveBeenCalledWith(1))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('shows a load failure without pretending there are no relationships', () => {
    render(
      <MemoryRouter>
        <DocumentRelationshipsPanel
          documentId={10}
          documentTitle="Incident Management Policy"
          edges={[]}
          loading={false}
          error="Doc Graph is not enabled in this environment."
          onChanged={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('relationships-error')).toHaveTextContent('not enabled')
  })
})
