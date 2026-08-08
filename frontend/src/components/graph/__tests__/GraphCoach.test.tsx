/**
 * GraphCoach + orientation mount smoke (X-2).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { DocumentEdge } from '../../../api/documentGraphClient'
import { DocumentRelationshipsPanel } from '../../../pages/DocumentRelationshipsPanel'
import { GraphCoach } from '../GraphCoach'
import { GraphOrientationToggle } from '../GraphOrientationToggle'
import { resetCoach } from '../graphCoachHelpers'

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
  graph_coach: false,
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

describe('GraphCoach smoke mount', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flagState.document_graph_heuristic_propose = false
    flagState.document_graph_map_view = false
    flagState.document_graph_dnd_propose = false
    flagState.graph_coach = false
    localStorage.clear()
    resetCoach('document_relationships')
    apiGet.mockResolvedValue({ data: { id: 20, title: 'Incident Reporting SOP' } })
    graph.getCitationStaleness.mockResolvedValue({ data: { edge_id: 1, status: 'unchanged' } })
  })

  it('hides GraphCoach when graph_coach is off', () => {
    renderPanel([edge({ id: 1 })])
    expect(screen.queryByTestId('graph-coach-document_relationships')).not.toBeInTheDocument()
  })

  it('shows GraphCoach when graph_coach is on and advances steps', () => {
    flagState.graph_coach = true
    render(
      <GraphCoach surface="document_relationships" storage={localStorage} />,
    )
    expect(screen.getByTestId('graph-coach-document_relationships')).toBeInTheDocument()
    expect(screen.getByTestId('graph-coach-step-document_relationships-orient')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('graph-coach-next-document_relationships'))
    expect(screen.getByTestId('graph-coach-step-document_relationships-roles')).toBeInTheDocument()
  })

  it('dismisses coach and stays hidden on remount', () => {
    flagState.graph_coach = true
    const { unmount } = render(
      <GraphCoach surface="document_relationships" storage={localStorage} />,
    )
    fireEvent.click(screen.getByTestId('graph-coach-skip-document_relationships'))
    expect(screen.queryByTestId('graph-coach-document_relationships')).not.toBeInTheDocument()
    unmount()
    render(<GraphCoach surface="document_relationships" storage={localStorage} />)
    expect(screen.queryByTestId('graph-coach-document_relationships')).not.toBeInTheDocument()
  })

  it('mounts coach on Relationships panel when flag on', async () => {
    flagState.graph_coach = true
    renderPanel([edge({ id: 1 })])
    expect(await screen.findByTestId('graph-coach-document_relationships')).toBeInTheDocument()
  })
})

describe('GraphOrientationToggle smoke', () => {
  beforeEach(() => {
    flagState.graph_coach = false
    localStorage.clear()
  })

  it('hides orientation toggle when graph_coach is off', () => {
    render(<GraphOrientationToggle surface="document_relationships" />)
    expect(
      screen.queryByTestId('graph-orientation-toggle-document_relationships'),
    ).not.toBeInTheDocument()
  })

  it('swaps horizontal/vertical when flag on', () => {
    flagState.graph_coach = true
    const onChange = vi.fn()
    render(
      <GraphOrientationToggle
        surface="document_relationships"
        value="horizontal"
        onChange={onChange}
      />,
    )
    expect(
      screen.getByTestId('graph-orientation-toggle-document_relationships'),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('graph-orientation-document_relationships-vertical'))
    expect(onChange).toHaveBeenCalledWith('vertical')
  })

  it('shows orientation toggle on map view when coach flag on', async () => {
    flagState.graph_coach = true
    flagState.document_graph_map_view = true
    renderPanel([edge({ id: 1 })])
    fireEvent.click(await screen.findByTestId('relationships-view-map'))
    expect(
      await screen.findByTestId('graph-orientation-toggle-document_relationships'),
    ).toBeInTheDocument()
    expect(screen.getByTestId('relationships-map-view')).toHaveAttribute(
      'data-orientation',
      'horizontal',
    )
    fireEvent.click(screen.getByTestId('graph-orientation-document_relationships-vertical'))
    expect(screen.getByTestId('relationships-map-view')).toHaveAttribute(
      'data-orientation',
      'vertical',
    )
  })
})
