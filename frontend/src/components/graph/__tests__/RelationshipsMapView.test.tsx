import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { DocumentEdge } from '../../../api/documentGraphClient'
import { DocumentRelationshipsPanel } from '../../../pages/DocumentRelationshipsPanel'

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

const flagState: Record<string, boolean> = {
  document_graph_heuristic_propose: false,
  document_graph_map_view: false,
}

vi.mock('../../../api/client', () => ({
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
      <Routes>
        <Route
          path="/"
          element={
            <DocumentRelationshipsPanel
              documentId={10}
              documentTitle="Incident Management Policy"
              edges={edges}
              loading={false}
              error={null}
              onChanged={vi.fn()}
            />
          }
        />
        <Route
          path="/documents/:documentId"
          element={<p data-testid="relationship-map-destination">Document detail</p>}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RelationshipsMapView flag gating via DocumentRelationshipsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flagState.document_graph_heuristic_propose = false
    flagState.document_graph_map_view = false
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

    await waitFor(() =>
      expect(screen.getByTestId('relationships-map-legend-20')).toHaveTextContent(
        'Incident Reporting SOP',
      ),
    )
  })

  it('keeps accessible documents with missing titles distinct from hidden documents', async () => {
    flagState.document_graph_map_view = true
    apiGet.mockResolvedValue({ data: { id: 20 } })
    renderPanel([edge({ id: 1 })])

    fireEvent.click(await screen.findByTestId('relationships-view-map'))

    expect(await screen.findByTestId('relationships-map-legend-20')).toHaveTextContent(
      'Document #20',
    )
    expect(screen.queryByText(/not available to you/)).not.toBeInTheDocument()
  })

  it('navigates map nodes through the client-side router', async () => {
    flagState.document_graph_map_view = true
    renderPanel([edge({ id: 1 })])

    fireEvent.click(await screen.findByTestId('relationships-view-map'))
    fireEvent.click(await screen.findByTestId('relationships-map-node-20'))

    expect(await screen.findByTestId('relationship-map-destination')).toBeInTheDocument()
  })
})
