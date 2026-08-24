/**
 * DocumentStructureMap page — flag-off + cascade aggregate mount smoke (NS-EXP / W8).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DocumentStructureMap from '../../../pages/DocumentStructureMap'
import { resetCoach } from '../graphCoachHelpers'

const getCascade = vi.fn()

const flagState: Record<string, boolean> = {
  document_graph: false,
  document_graph_structure_map: false,
  graph_coach: false,
}

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn() },
  documentGraphApi: {
    getCascade: (...args: unknown[]) => getCascade(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
}))

function cascadePayload(overrides: Record<string, unknown> = {}) {
  return {
    documents: [
      {
        document_id: 10,
        title: 'IM Policy',
        reference: 'DOC-10',
        pel_doc_ref: 'PEL-HSEQ-2001',
        cascade_level: 2,
        document_type: 'policy',
        href: '/documents/10',
        readable: true,
        parent_document_id: null,
        parent_pel: null,
      },
      {
        document_id: 20,
        title: 'Reporting SOP',
        reference: 'DOC-20',
        pel_doc_ref: 'PEL-HSEQ-3001',
        cascade_level: 3,
        document_type: 'sop',
        href: '/documents/20',
        readable: true,
        parent_document_id: 10,
        parent_pel: 'PEL-HSEQ-2001',
      },
    ],
    edges: [
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
    bands: [
      { level: 1, label: 'L1', count: 0 },
      { level: 2, label: 'L2', count: 1 },
      { level: 3, label: 'L3', count: 1 },
      { level: 4, label: 'L4', count: 0 },
      { level: 5, label: 'L5', count: 0 },
      { level: null, label: 'unset', count: 0 },
    ],
    orphans: {
      unimplemented_policy_ids: [],
      unparented_ids: [],
      uncontrolled_record_ids: [],
      unimplemented_policy_count: 0,
      unparented_count: 0,
      uncontrolled_record_count: 0,
    },
    returned_documents: 2,
    returned_edges: 1,
    ...overrides,
  }
}

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
    getCascade.mockReset()
    flagState.document_graph = false
    flagState.document_graph_structure_map = false
    flagState.graph_coach = false
    resetCoach('document_structure_map', localStorage)
  })

  it('redirects to library when document_graph_structure_map is off', () => {
    renderAt()
    expect(screen.getByTestId('documents-fallback')).toBeInTheDocument()
    expect(screen.queryByTestId('document-structure-map')).not.toBeInTheDocument()
    expect(getCascade).not.toHaveBeenCalled()
  })

  it('does not fetch when structure map is on but master document_graph is off', async () => {
    flagState.document_graph_structure_map = true
    flagState.document_graph = false
    renderAt()
    expect(screen.getByTestId('document-structure-map')).toBeInTheDocument()
    await waitFor(() => {
      expect(getCascade).not.toHaveBeenCalled()
    })
  })

  it('loads the cascade aggregate once and mounts coach when flags are on', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    flagState.graph_coach = true
    getCascade.mockResolvedValue({ data: cascadePayload() })

    renderAt()

    expect(await screen.findByTestId('document-structure-map')).toBeInTheDocument()
    expect(await screen.findByTestId('graph-coach-document_structure_map')).toBeInTheDocument()
    expect(await screen.findByTestId('structure-map-doc-10')).toBeInTheDocument()
    expect(await screen.findByTestId('structure-map-level-10')).toHaveTextContent('L2')
    expect(await screen.findByTestId('structure-map-parent-20')).toHaveTextContent(
      'Parent PEL-HSEQ-2001',
    )
    await waitFor(() => {
      expect(getCascade).toHaveBeenCalledTimes(1)
    })
    expect(await screen.findByTestId('relationships-map-view')).toBeInTheDocument()
    expect(screen.getByTestId('structure-map-bands')).toBeInTheDocument()
  })

  it('filters the picker by cascade band without a second fetch', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    getCascade.mockResolvedValue({ data: cascadePayload() })

    renderAt()

    await screen.findByTestId('structure-map-doc-10')
    fireEvent.click(screen.getByTestId('structure-map-band-3'))
    expect(screen.queryByTestId('structure-map-doc-10')).not.toBeInTheDocument()
    expect(screen.getByTestId('structure-map-doc-20')).toBeInTheDocument()
    expect(getCascade).toHaveBeenCalledTimes(1)
  })

  it('does not claim missing implements when a cascade band has no documents', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    getCascade.mockResolvedValue({ data: cascadePayload() })

    renderAt()

    await screen.findByTestId('structure-map-doc-10')
    fireEvent.click(screen.getByTestId('structure-map-band-1'))
    expect(await screen.findByTestId('structure-map-empty')).toHaveTextContent(
      /No documents in this cascade band/i,
    )
    expect(screen.getByTestId('structure-map-empty').textContent?.toLowerCase()).not.toContain(
      'confirmed implements',
    )
  })

  it('lists roots first and gives filtered-empty copy', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    getCascade.mockResolvedValue({ data: cascadePayload() })

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

  it('surfaces cascade aggregate failures honestly', async () => {
    flagState.document_graph = true
    flagState.document_graph_structure_map = true
    getCascade.mockRejectedValue(new Error('cascade service unavailable'))

    renderAt()

    expect(await screen.findByTestId('structure-map-error')).toHaveTextContent(
      'cascade service unavailable',
    )
  })
})
