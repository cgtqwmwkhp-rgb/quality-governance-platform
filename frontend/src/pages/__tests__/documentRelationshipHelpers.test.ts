import { describe, expect, it } from 'vitest'
import type { DocumentEdge, DocumentEdgeType } from '../../api/documentGraphClient'
import {
  buildDocumentEdgePayload,
  counterpartDocumentIds,
  CREATE_WIZARD_DOCUMENT_EDGE_TYPES,
  DOCUMENT_EDGE_TYPE_META,
  findConflictingEdge,
  isActiveDocumentEdge,
  isPendingDocumentEdge,
  resolveDocumentEdge,
  resolveDocumentRelationshipAmbientCounts,
  shouldShowDocumentRelationshipChips,
  summariseDocumentRelationships,
} from '../documentRelationshipHelpers'

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

describe('CREATE_WIZARD_DOCUMENT_EDGE_TYPES', () => {
  it('offers authorship types without references (citations stay on detail)', () => {
    expect([...CREATE_WIZARD_DOCUMENT_EDGE_TYPES]).toEqual([
      'implements',
      'requires_record',
      'related_to',
      'conflicts_with',
    ])
    expect(CREATE_WIZARD_DOCUMENT_EDGE_TYPES).not.toContain('references')
  })
})

describe('resolveDocumentEdge', () => {
  it('reads a directed edge from the source side', () => {
    const resolved = resolveDocumentEdge(10, edge({ id: 1, dst_pel_doc_ref: 'PEL-POL-001' }))
    expect(resolved.direction).toBe('outbound')
    expect(resolved.counterpartDocumentId).toBe(20)
    expect(resolved.counterpartPelDocRef).toBe('PEL-POL-001')
    expect(resolved.relationLabel).toBe('Implements')
  })

  it('inverts the label when read from the destination side', () => {
    const resolved = resolveDocumentEdge(20, edge({ id: 1, src_pel_doc_ref: 'PEL-SOP-009' }))
    expect(resolved.direction).toBe('inbound')
    expect(resolved.counterpartDocumentId).toBe(10)
    expect(resolved.counterpartPelDocRef).toBe('PEL-SOP-009')
    expect(resolved.relationLabel).toBe('Implemented by')
  })

  it('treats canonical peer types as directionless from either side', () => {
    for (const edgeType of ['related_to', 'conflicts_with'] as DocumentEdgeType[]) {
      expect(resolveDocumentEdge(10, edge({ id: 1, edge_type: edgeType })).direction).toBe('peer')
      expect(resolveDocumentEdge(20, edge({ id: 1, edge_type: edgeType })).direction).toBe('peer')
      expect(resolveDocumentEdge(20, edge({ id: 1, edge_type: edgeType })).relationLabel).toBe(
        DOCUMENT_EDGE_TYPE_META[edgeType].outbound,
      )
    }
  })
})

describe('edge status predicates', () => {
  it('treats proposed and needs_review as the confirm queue', () => {
    expect(isPendingDocumentEdge(edge({ id: 1, status: 'proposed' }))).toBe(true)
    expect(isPendingDocumentEdge(edge({ id: 1, status: 'needs_review' }))).toBe(true)
    expect(isPendingDocumentEdge(edge({ id: 1, status: 'confirmed' }))).toBe(false)
    expect(isPendingDocumentEdge(edge({ id: 1, status: 'rejected' }))).toBe(false)
  })

  it('treats rejected and soft-deleted edges as inert', () => {
    expect(isActiveDocumentEdge(edge({ id: 1 }))).toBe(true)
    expect(isActiveDocumentEdge(edge({ id: 1, status: 'rejected' }))).toBe(false)
    expect(
      isActiveDocumentEdge(edge({ id: 1, deleted_at: '2026-08-02T10:00:00Z' })),
    ).toBe(false)
  })
})

describe('summariseDocumentRelationships', () => {
  const edges: DocumentEdge[] = [
    edge({ id: 1, src_document_id: 10, dst_document_id: 20 }),
    edge({ id: 2, src_document_id: 30, dst_document_id: 10 }),
    edge({ id: 3, src_document_id: 10, dst_document_id: 40, edge_type: 'related_to' }),
    edge({ id: 4, src_document_id: 10, dst_document_id: 50, status: 'proposed' }),
    edge({ id: 5, src_document_id: 10, dst_document_id: 60, status: 'needs_review' }),
    edge({ id: 6, src_document_id: 10, dst_document_id: 70, status: 'rejected' }),
    edge({ id: 7, src_document_id: 10, dst_document_id: 80, edge_type: 'conflicts_with' }),
  ]

  it('counts confirmed edges by direction and keeps rejected edges out', () => {
    const summary = summariseDocumentRelationships(10, edges)
    expect(summary.total).toBe(6)
    expect(summary.confirmed).toBe(4)
    expect(summary.pending).toBe(2)
    expect(summary.outbound).toBe(1)
    expect(summary.inbound).toBe(1)
    expect(summary.peers).toBe(2)
    expect(summary.conflicts).toBe(1)
  })

  it('is all zeroes for a document with no relationships', () => {
    expect(summariseDocumentRelationships(10, [])).toEqual({
      total: 0,
      confirmed: 0,
      pending: 0,
      outbound: 0,
      inbound: 0,
      peers: 0,
      conflicts: 0,
    })
  })

  it('counts a pending conflict as a conflict, not only as queue depth', () => {
    const summary = summariseDocumentRelationships(10, [
      edge({ id: 1, edge_type: 'conflicts_with', status: 'proposed' }),
    ])
    expect(summary.conflicts).toBe(1)
    expect(summary.pending).toBe(1)
    expect(summary.confirmed).toBe(0)
  })
})

describe('buildDocumentEdgePayload', () => {
  it('puts the open document on the source side for an outbound edge', () => {
    expect(
      buildDocumentEdgePayload({
        documentId: 10,
        counterpartDocumentId: 20,
        edgeType: 'implements',
        direction: 'outbound',
        isPrimaryParent: true,
      }),
    ).toEqual({
      src_document_id: 10,
      dst_document_id: 20,
      edge_type: 'implements',
      is_primary_parent: true,
      status: 'confirmed',
      created_method: 'manual',
    })
  })

  it('swaps the endpoints for an inbound edge', () => {
    const payload = buildDocumentEdgePayload({
      documentId: 10,
      counterpartDocumentId: 20,
      edgeType: 'requires_record',
      direction: 'inbound',
    })
    expect(payload.src_document_id).toBe(20)
    expect(payload.dst_document_id).toBe(10)
    expect(payload.is_primary_parent).toBe(false)
  })

  it('ignores direction for undirected peer types', () => {
    const payload = buildDocumentEdgePayload({
      documentId: 10,
      counterpartDocumentId: 20,
      edgeType: 'related_to',
      direction: 'inbound',
    })
    expect(payload.src_document_id).toBe(10)
    expect(payload.dst_document_id).toBe(20)
  })

  it('never sets is_primary_parent outside implements', () => {
    for (const edgeType of ['requires_record', 'references', 'related_to', 'conflicts_with'] as
      DocumentEdgeType[]) {
      const payload = buildDocumentEdgePayload({
        documentId: 10,
        counterpartDocumentId: 20,
        edgeType,
        isPrimaryParent: true,
      })
      expect(payload.is_primary_parent).toBe(false)
    }
  })

  it('only confirms a hand-authored edge; machine methods stay proposed', () => {
    expect(
      buildDocumentEdgePayload({
        documentId: 10,
        counterpartDocumentId: 20,
        edgeType: 'implements',
      }).status,
    ).toBe('confirmed')

    for (const createdMethod of ['ai', 'heuristic', 'extracted', 'auto'] as const) {
      const payload = buildDocumentEdgePayload({
        documentId: 10,
        counterpartDocumentId: 20,
        edgeType: 'implements',
        createdMethod,
      })
      expect(payload.status).toBe('proposed')
      expect(payload.created_method).toBe(createdMethod)
    }
  })

  it('trims the rationale and omits it when blank', () => {
    expect(
      buildDocumentEdgePayload({
        documentId: 10,
        counterpartDocumentId: 20,
        edgeType: 'references',
        rationale: '  Cited in section 4  ',
      }).rationale,
    ).toBe('Cited in section 4')

    expect(
      'rationale' in
        buildDocumentEdgePayload({
          documentId: 10,
          counterpartDocumentId: 20,
          edgeType: 'references',
          rationale: '   ',
        }),
    ).toBe(false)
  })

  it('refuses a self-link', () => {
    expect(() =>
      buildDocumentEdgePayload({
        documentId: 10,
        counterpartDocumentId: 10,
        edgeType: 'related_to',
      }),
    ).toThrow('cannot be related to itself')
  })
})

describe('findConflictingEdge', () => {
  const payload = buildDocumentEdgePayload({
    documentId: 10,
    counterpartDocumentId: 20,
    edgeType: 'implements',
    direction: 'outbound',
  })

  it('finds the live edge already holding the slot', () => {
    const existing = edge({ id: 1, src_document_id: 10, dst_document_id: 20 })
    expect(findConflictingEdge([existing], payload)).toBe(existing)
  })

  it('still finds a rejected edge, because it keeps the unique slot', () => {
    const rejected = edge({ id: 1, src_document_id: 10, dst_document_id: 20, status: 'rejected' })
    expect(findConflictingEdge([rejected], payload)).toBe(rejected)
  })

  it('ignores unlinked edges so the pair can be re-authored', () => {
    const unlinked = edge({
      id: 1,
      src_document_id: 10,
      dst_document_id: 20,
      deleted_at: '2026-08-02T10:00:00Z',
    })
    expect(findConflictingEdge([unlinked], payload)).toBeNull()
  })

  it('does not treat the opposite direction of a directed type as a duplicate', () => {
    const reverse = edge({ id: 1, src_document_id: 20, dst_document_id: 10 })
    expect(findConflictingEdge([reverse], payload)).toBeNull()
  })

  it('treats either ordering of a peer type as the same edge', () => {
    const peerPayload = buildDocumentEdgePayload({
      documentId: 10,
      counterpartDocumentId: 20,
      edgeType: 'related_to',
    })
    const stored = edge({ id: 1, src_document_id: 20, dst_document_id: 10, edge_type: 'related_to' })
    expect(findConflictingEdge([stored], peerPayload)).toBe(stored)
  })

  it('ignores a different edge type between the same pair', () => {
    const other = edge({ id: 1, src_document_id: 10, dst_document_id: 20, edge_type: 'references' })
    expect(findConflictingEdge([other], payload)).toBeNull()
  })
})

describe('counterpartDocumentIds', () => {
  it('dedupes counterparts and excludes the open document', () => {
    const ids = counterpartDocumentIds(10, [
      edge({ id: 1, src_document_id: 10, dst_document_id: 20 }),
      edge({ id: 2, src_document_id: 20, dst_document_id: 10 }),
      edge({ id: 3, src_document_id: 30, dst_document_id: 10 }),
    ])
    expect(ids).toEqual([20, 30])
  })
})

describe('resolveDocumentRelationshipAmbientCounts', () => {
  const summary = { inbound: 2, outbound: 1, peers: 3 }

  it('returns ambient counts when the Doc Graph flag is on and listEdges succeeded', () => {
    expect(resolveDocumentRelationshipAmbientCounts(true, null, summary)).toEqual(summary)
  })

  it('attaches coverage honesty when the spine is sparse', () => {
    expect(
      resolveDocumentRelationshipAmbientCounts(
        true,
        null,
        summary,
        '0 of 4 expected relationship roles recorded',
      ),
    ).toEqual({
      ...summary,
      coverageHonesty: '0 of 4 expected relationship roles recorded',
    })
  })

  it('hides ambient counts when listEdges failed (even if summary still has zeros)', () => {
    expect(
      resolveDocumentRelationshipAmbientCounts(true, 'Failed to load relationships', {
        inbound: 0,
        outbound: 0,
        peers: 0,
      }),
    ).toBeNull()
  })

  it('stays hidden when the Doc Graph flag is closed', () => {
    expect(resolveDocumentRelationshipAmbientCounts(false, null, summary)).toBeNull()
    expect(
      resolveDocumentRelationshipAmbientCounts(
        false,
        null,
        summary,
        '0 of 4 expected relationship roles recorded',
      ),
    ).toBeNull()
  })
})

describe('shouldShowDocumentRelationshipChips', () => {
  it('shows header chips only while the flag is on and there is no listEdges error', () => {
    expect(shouldShowDocumentRelationshipChips(true, null)).toBe(true)
    expect(shouldShowDocumentRelationshipChips(true, undefined)).toBe(true)
    expect(shouldShowDocumentRelationshipChips(true, 'boom')).toBe(false)
    expect(shouldShowDocumentRelationshipChips(false, null)).toBe(false)
  })
})
