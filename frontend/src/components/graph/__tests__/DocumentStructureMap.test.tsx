/**
 * DocumentStructureMap page — flag-off + coach/map mount smoke (DG-3).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DocumentStructureMap from '../../../pages/DocumentStructureMap'
import { resetCoach } from '../graphCoachHelpers'

const apiGet = vi.fn()
const listEdges = vi.fn()

const flagState: Record<string, boolean> = {
  document_graph: false,
  document_graph_structure_map: false,
  graph_coach: false,
}

vi.mock('../../../api/client', () => ({
  default: { get: (...args: unknown[]) => apiGet(...args) },
  documentGraphApi: {
    listEdges: (...args: unknown[]) => listEdges(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
}))

function renderAt(path = '/documents/structure') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/documents" element={<div data-testid="documents-fallback">Library</div>} />
        <Route path="/documents/structure" element={<DocumentStructureMap />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DocumentStructureMap flag gating', () => {
  beforeEach(() => {
    apiGet.mockReset()
    listEdges.mockReset()
    flagState.document_graph = false
    flagState.document_graph_structure_map = false
    flagState.graph_coach = false
    resetCoach('document_structure_map', localStorage)
  })

  it('redirects to library when document_graph_structure_map is off', () => {
    renderAt()
    expect(screen.getByTestId('documents-fallback')).toBeInTheDocument()
    expect(screen.queryByTestId('document-structure-map')).not.toBeInTheDocument()
    expect(apiGet).not.toHaveBeenCalled()
    expect(listEdges).not.toHaveBeenCalled()
  })

  it('does not fetch when structure map is on but master document_graph is off', async () => {
    flagState.document_graph_structure_map = true
    flagState.document_graph = false
    renderAt()
    expect(screen.getByTestId('document-structure-map')).toBeInTheDocument()
    await waitFor(() => {
      expect(apiGet).not.toHaveBeenCalled()
      expect(listEdges).not.toHaveBeenCalled()
    })
  })

  it('loads library implements edges and mounts coach when flags are on', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    flagState.graph_coach = true
    apiGet.mockResolvedValue({
      data: {
        items: [
          { id: 10, title: 'IM Policy', reference_number: 'POL-10', document_type: 'policy' },
          { id: 20, title: 'Reporting SOP', reference_number: 'SOP-20', document_type: 'sop' },
        ],
      },
    })
    listEdges.mockImplementation((documentId: number) => {
      if (documentId === 10) {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 1,
                tenant_id: 1,
                src_document_id: 20,
                dst_document_id: 10,
                edge_type: 'implements',
                is_primary_parent: true,
                status: 'confirmed',
                created_method: 'manual',
                created_at: '2026-08-01T10:00:00Z',
                updated_at: '2026-08-01T10:00:00Z',
              },
            ],
            total: 1,
          },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0 } })
    })

    renderAt()

    expect(await screen.findByTestId('document-structure-map')).toBeInTheDocument()
    expect(await screen.findByTestId('graph-coach-document_structure_map')).toBeInTheDocument()
    expect(await screen.findByTestId('structure-map-doc-10')).toBeInTheDocument()
    await waitFor(() => {
      expect(apiGet).toHaveBeenCalled()
      expect(listEdges).toHaveBeenCalled()
    })
    expect(await screen.findByTestId('relationships-map-view')).toBeInTheDocument()
  })

  it('loads every page with the API-supported page size', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    const firstPage = Array.from({ length: 100 }, (_, index) => ({
      id: index + 1,
      title: `Document ${index + 1}`,
    }))
    apiGet.mockImplementation((url: string) => {
      if (url.includes('page=1&')) {
        return Promise.resolve({
          data: { items: firstPage, total: 101, page: 1, page_size: 100, pages: 2 },
        })
      }
      return Promise.resolve({
        data: {
          items: [{ id: 101, title: 'Document 101' }],
          total: 101,
          page: 2,
          page_size: 100,
          pages: 2,
        },
      })
    })
    listEdges.mockResolvedValue({ data: { items: [], total: 0 } })

    renderAt()

    await waitFor(() => {
      expect(screen.getByTestId('structure-map-doc-count')).toHaveTextContent('101 documents')
    })
    expect(apiGet).toHaveBeenNthCalledWith(1, '/api/v1/documents/?page=1&page_size=100')
    expect(apiGet).toHaveBeenNthCalledWith(2, '/api/v1/documents/?page=2&page_size=100')
    expect(screen.getByTestId('structure-map-doc-101')).toBeInTheDocument()
  })

  it('lists roots first and gives filtered-empty copy', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    apiGet.mockResolvedValue({
      data: {
        items: [
          { id: 20, title: 'Reporting SOP' },
          { id: 10, title: 'IM Policy' },
        ],
      },
    })
    listEdges.mockImplementation((documentId: number) =>
      Promise.resolve({
        data: {
          items:
            documentId === 20
              ? [
                  {
                    id: 1,
                    tenant_id: 1,
                    src_document_id: 20,
                    dst_document_id: 10,
                    edge_type: 'implements',
                    is_primary_parent: true,
                    status: 'confirmed',
                    created_method: 'manual',
                    created_at: '2026-08-01T10:00:00Z',
                    updated_at: '2026-08-01T10:00:00Z',
                  },
                ]
              : [],
          total: documentId === 20 ? 1 : 0,
        },
      }),
    )

    renderAt()

    const list = await screen.findByTestId('structure-map-doc-list')
    await waitFor(() => {
      expect(list.querySelector('button')).toHaveAttribute('data-testid', 'structure-map-doc-10')
    })
    fireEvent.change(screen.getByTestId('structure-map-filter'), {
      target: { value: 'does-not-exist' },
    })
    expect(await screen.findByText('No documents match your filter.')).toBeInTheDocument()
  })

  it('surfaces partial edge fetch failures without discarding successful results', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    apiGet.mockResolvedValue({
      data: {
        items: [
          { id: 10, title: 'IM Policy' },
          { id: 20, title: 'Reporting SOP' },
        ],
      },
    })
    listEdges.mockImplementation((documentId: number) => {
      if (documentId === 20) return Promise.reject(new Error('edge service unavailable'))
      return Promise.resolve({ data: { items: [], total: 0 } })
    })

    renderAt()

    expect(await screen.findByTestId('structure-map-error')).toHaveTextContent(
      'Failed to load confirmed implements edges for 1 of 2 documents: edge service unavailable',
    )
    expect(screen.getByTestId('structure-map-doc-10')).toBeInTheDocument()
  })
})
