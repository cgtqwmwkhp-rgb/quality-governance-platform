import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { DocumentEdge } from '../../../api/documentGraphClient'
import { DocumentRelationshipsPanel } from '../../../pages/DocumentRelationshipsPanel'

const apiGet = vi.fn()
const graph = {
  createEdge: vi.fn(),
  proposeTypedEdge: vi.fn(),
  confirmEdge: vi.fn(),
  rejectEdge: vi.fn(),
  deleteEdge: vi.fn(),
  confirmEdges: vi.fn(),
  proposeHeuristics: vi.fn(),
  getCitationStaleness: vi.fn(),
}

const flagState: Record<string, boolean> = {
  document_graph_heuristic_propose: false,
  document_graph_map_view: false,
  document_graph_dnd_propose: false,
}

vi.mock('../../../api/client', () => ({
  default: { get: (...args: unknown[]) => apiGet(...args) },
  documentGraphApi: {
    createEdge: (...args: unknown[]) => graph.createEdge(...args),
    proposeTypedEdge: (...args: unknown[]) => graph.proposeTypedEdge(...args),
    confirmEdge: (...args: unknown[]) => graph.confirmEdge(...args),
    rejectEdge: (...args: unknown[]) => graph.rejectEdge(...args),
    deleteEdge: (...args: unknown[]) => graph.deleteEdge(...args),
    confirmEdges: (...args: unknown[]) => graph.confirmEdges(...args),
    proposeHeuristics: (...args: unknown[]) => graph.proposeHeuristics(...args),
    getCitationStaleness: (...args: unknown[]) => graph.getCitationStaleness(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
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

function renderPanel(edges: DocumentEdge[]) {
  return render(
    <MemoryRouter>
      <DocumentRelationshipsPanel
        documentId={10}
        documentTitle="Incident Management Policy"
        edges={edges}
        loading={false}
        error={null}
        onChanged={vi.fn()}
      />
    </MemoryRouter>,
  )
}

describe('RelationshipsMapView flag gating via DocumentRelationshipsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flagState.document_graph_heuristic_propose = false
    flagState.document_graph_map_view = false
    flagState.document_graph_dnd_propose = false
    apiGet.mockResolvedValue({ data: { id: 20, title: 'Incident Reporting SOP' } })
    graph.getCitationStaleness.mockResolvedValue({ data: { edge_id: 1, status: 'unchanged' } })
  })

  it('hides Map|List toggle and map panel when document_graph_map_view is off', async () => {
    renderPanel([edge({ id: 1 })])
    expect(await screen.findByText('Incident Reporting SOP')).toBeInTheDocument()
    expect(screen.queryByTestId('relationships-view-toggle')).not.toBeInTheDocument()
    expect(screen.queryByTestId('relationships-map-view')).not.toBeInTheDocument()
    expect(screen.getByTestId('relationships-confirmed-list')).toBeInTheDocument()
  })

  it('shows Map|List toggle and switches to hub map when flag is on', async () => {
    flagState.document_graph_map_view = true
    renderPanel([edge({ id: 1 })])

    expect(await screen.findByTestId('relationships-view-toggle')).toBeInTheDocument()
    expect(screen.getByTestId('relationships-confirmed-list')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('relationships-view-map'))
    expect(await screen.findByTestId('relationships-map-view')).toBeInTheDocument()
    expect(screen.getByTestId('relationships-map-hub')).toBeInTheDocument()
    expect(screen.queryByTestId('relationships-confirmed-list')).not.toBeInTheDocument()
    expect(screen.queryByTestId('relationships-dnd-tray')).not.toBeInTheDocument()

    await waitFor(() =>
      expect(screen.getByTestId('relationships-map-legend-20')).toHaveTextContent(
        'Incident Reporting SOP',
      ),
    )
  })

  it('shows DnD tray + drop zone when dnd propose flag is on in map view', async () => {
    flagState.document_graph_map_view = true
    flagState.document_graph_dnd_propose = true
    apiGet.mockImplementation((url: string, config?: { params?: unknown }) => {
      if (String(url) === '/api/v1/documents/' || config?.params) {
        return Promise.resolve({
          data: {
            items: [{ id: 20, title: 'Incident Reporting SOP', reference_number: 'SOP-20' }],
          },
        })
      }
      return Promise.resolve({ data: { id: 20, title: 'Incident Reporting SOP' } })
    })
    graph.proposeTypedEdge.mockResolvedValue({
      data: edge({ id: 99, status: 'proposed', src_document_id: 10, dst_document_id: 20 }),
    })

    renderPanel([edge({ id: 1 })])
    fireEvent.click(await screen.findByTestId('relationships-view-map'))

    expect(await screen.findByTestId('relationships-dnd-tray')).toBeInTheDocument()
    expect(screen.getByTestId('relationships-map-drop-zone')).toBeInTheDocument()
    expect(screen.getByTestId('relationships-dnd-edge-type')).toHaveValue('related_to')

    fireEvent.change(screen.getByTestId('relationships-dnd-search'), {
      target: { value: 'Incident' },
    })
    expect(await screen.findByTestId('relationships-dnd-tray-item-20')).toBeInTheDocument()

    const dropZone = screen.getByTestId('relationships-map-drop-zone')
    fireEvent.drop(dropZone, {
      dataTransfer: {
        getData: (type: string) =>
          type === 'application/x-qgp-library-document' || type === 'text/plain'
            ? JSON.stringify({ documentId: 20, title: 'Incident Reporting SOP' })
            : '',
        types: ['application/x-qgp-library-document'],
      },
      preventDefault: () => undefined,
      stopPropagation: () => undefined,
    })

    await waitFor(() => {
      expect(graph.proposeTypedEdge).toHaveBeenCalledWith(
        expect.objectContaining({
          src_document_id: 10,
          dst_document_id: 20,
          edge_type: 'related_to',
          status: 'proposed',
          created_method: 'manual',
        }),
      )
    })
    expect(graph.createEdge).not.toHaveBeenCalled()
  })
})
