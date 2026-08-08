import { describe, expect, it } from 'vitest'
import type { DocumentEdge } from '../../../api/documentGraphClient'
import {
  LIBRARY_DOCUMENT_DRAG_MIME,
  buildDndProposeEdgePayload,
  dndProposeDirection,
  parseLibraryDocumentDrag,
  parseLibraryDocumentDragData,
  resolveDndProposeDrop,
  serializeLibraryDocumentDrag,
  shouldEnableLibraryDocumentDrag,
  shouldEnableRelationshipsMapDnd,
} from '../documentGraphDndHelpers'

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

describe('documentGraphDndHelpers', () => {
  it('gates Documents tray drag and map drop on the DnD programme flag', () => {
    expect(shouldEnableLibraryDocumentDrag(false)).toBe(false)
    expect(shouldEnableLibraryDocumentDrag(true)).toBe(true)
    expect(shouldEnableRelationshipsMapDnd(false)).toBe(false)
    expect(shouldEnableRelationshipsMapDnd(true)).toBe(true)
  })

  it('serializes and parses library document drag payloads', () => {
    const raw = serializeLibraryDocumentDrag({
      documentId: 42,
      title: 'Incident Reporting SOP',
      reference: 'SOP-42',
    })
    expect(JSON.parse(raw)).toEqual({
      documentId: 42,
      title: 'Incident Reporting SOP',
      reference: 'SOP-42',
    })
    expect(parseLibraryDocumentDragData(raw)).toEqual({
      documentId: 42,
      title: 'Incident Reporting SOP',
      reference: 'SOP-42',
    })
    expect(parseLibraryDocumentDragData('not-json')).toBeNull()
    expect(parseLibraryDocumentDragData('{"documentId":0}')).toBeNull()
  })

  it('reads custom MIME first then text/plain fallback from DataTransfer', () => {
    const store: Record<string, string> = {
      [LIBRARY_DOCUMENT_DRAG_MIME]: serializeLibraryDocumentDrag({ documentId: 7, title: 'A' }),
      'text/plain': serializeLibraryDocumentDrag({ documentId: 99, title: 'B' }),
    }
    const dt = {
      getData: (type: string) => store[type] ?? '',
    } as DataTransfer

    expect(parseLibraryDocumentDrag(dt)).toEqual({ documentId: 7, title: 'A' })

    delete store[LIBRARY_DOCUMENT_DRAG_MIME]
    expect(parseLibraryDocumentDrag(dt)).toEqual({ documentId: 99, title: 'B' })
    expect(parseLibraryDocumentDrag(null)).toBeNull()
  })

  it('uses inbound src for implements / requires_record and outbound otherwise', () => {
    expect(dndProposeDirection('implements')).toBe('inbound')
    expect(dndProposeDirection('requires_record')).toBe('inbound')
    expect(dndProposeDirection('related_to')).toBe('outbound')
    expect(dndProposeDirection('references')).toBe('outbound')
    expect(dndProposeDirection('conflicts_with')).toBe('outbound')
  })

  it('builds propose-only payloads and never auto-confirms', () => {
    const implementsPayload = buildDndProposeEdgePayload({
      hubDocumentId: 10,
      draggedDocumentId: 20,
      edgeType: 'implements',
    })
    expect(implementsPayload).toEqual({
      src_document_id: 20,
      dst_document_id: 10,
      edge_type: 'implements',
      is_primary_parent: false,
      status: 'proposed',
      created_method: 'manual',
      rationale: 'Proposed via drag-and-drop from Library tray',
    })

    const related = buildDndProposeEdgePayload({
      hubDocumentId: 10,
      draggedDocumentId: 30,
      edgeType: 'related_to',
    })
    expect(related.status).toBe('proposed')
    expect(related.src_document_id).toBe(10)
    expect(related.dst_document_id).toBe(30)

    expect(() =>
      buildDndProposeEdgePayload({
        hubDocumentId: 10,
        draggedDocumentId: 10,
        edgeType: 'related_to',
      }),
    ).toThrow(/itself/)
  })

  it('resolves drop success and rejects self / duplicate drops', () => {
    const ok = resolveDndProposeDrop({
      hubDocumentId: 10,
      dragged: { documentId: 20, title: 'SOP' },
      edgeType: 'related_to',
      existingEdges: [],
    })
    expect(ok.ok).toBe(true)
    if (ok.ok) {
      expect(ok.payload.status).toBe('proposed')
      expect(ok.payload.edge_type).toBe('related_to')
    }

    const self = resolveDndProposeDrop({
      hubDocumentId: 10,
      dragged: { documentId: 10 },
      edgeType: 'related_to',
      existingEdges: [],
    })
    expect(self.ok).toBe(false)

    const missing = resolveDndProposeDrop({
      hubDocumentId: 10,
      dragged: null,
      edgeType: 'related_to',
      existingEdges: [],
    })
    expect(missing.ok).toBe(false)

    const duplicate = resolveDndProposeDrop({
      hubDocumentId: 10,
      dragged: { documentId: 20 },
      edgeType: 'implements',
      existingEdges: [
        edge({
          id: 1,
          src_document_id: 20,
          dst_document_id: 10,
          edge_type: 'implements',
          status: 'proposed',
        }),
      ],
    })
    expect(duplicate.ok).toBe(false)
    if (!duplicate.ok) {
      expect(duplicate.reason).toMatch(/already exists/i)
    }
  })
})
