/**
 * Structure map helpers (DG-3).
 */
import { describe, expect, it } from 'vitest'
import type { DocumentEdge } from '../../../api/documentGraphClient'
import {
  STRUCTURE_MAP_DEFAULT_ORIENTATION,
  buildStructureMapLabels,
  buildStructureMapModel,
  dedupeDocumentEdgesById,
  filterConfirmedImplementsEdges,
  filterStructureMapDocumentsByBand,
  findStructureMapRootIds,
  mapCascadeDocumentsToStructureRefs,
  resolveStructureMapFocusId,
  shouldFetchDocumentStructureMap,
  shouldShowDocumentStructureMap,
  structureMapBandButtonLabel,
  structureMapEmptyCopy,
  structureMapLevelBadge,
} from '../documentStructureMapHelpers'

function edge(overrides: Partial<DocumentEdge> & { id: number }): DocumentEdge {
  return {
    tenant_id: 1,
    src_document_id: 10,
    dst_document_id: 20,
    edge_type: 'implements',
    is_primary_parent: true,
    status: 'confirmed',
    created_method: 'manual',
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

describe('documentStructureMapHelpers flag gates', () => {
  it('hides Structure map when programme flag is off', () => {
    expect(shouldShowDocumentStructureMap(false)).toBe(false)
    expect(shouldShowDocumentStructureMap(true)).toBe(true)
  })

  it('fetches only when master Doc Graph and Structure map are both on', () => {
    expect(shouldFetchDocumentStructureMap(false, true)).toBe(false)
    expect(shouldFetchDocumentStructureMap(true, false)).toBe(false)
    expect(shouldFetchDocumentStructureMap(true, true)).toBe(true)
  })
})

describe('documentStructureMapHelpers graph shaping', () => {
  it('keeps confirmed implements only and dedupes by id', () => {
    const edges = [
      edge({ id: 1 }),
      edge({ id: 1, src_document_id: 10, dst_document_id: 20 }),
      edge({ id: 2, edge_type: 'related_to', status: 'confirmed' }),
      edge({ id: 3, status: 'proposed' }),
      edge({ id: 4, deleted_at: '2026-08-02T00:00:00Z' }),
    ]
    expect(filterConfirmedImplementsEdges(edges).map((e) => e.id)).toEqual([1, 1])
    expect(dedupeDocumentEdgesById(filterConfirmedImplementsEdges(edges)).map((e) => e.id)).toEqual([
      1,
    ])
  })

  it('finds forest roots as parents that are never children', () => {
    const edges = [
      edge({ id: 1, src_document_id: 20, dst_document_id: 10 }), // 20 implements 10
      edge({ id: 2, src_document_id: 30, dst_document_id: 20 }), // 30 implements 20
    ]
    expect(findStructureMapRootIds(edges)).toEqual([10])
  })

  it('resolves focus preference, then root, then first document', () => {
    const docs = [
      { id: 20, title: 'Procedure' },
      { id: 10, title: 'Policy' },
      { id: 30, title: 'SOP' },
    ]
    expect(resolveStructureMapFocusId(30, docs, [10])).toBe(30)
    expect(resolveStructureMapFocusId(null, docs, [10])).toBe(10)
    expect(resolveStructureMapFocusId(999, docs, [])).toBe(20)
    expect(resolveStructureMapFocusId(null, [], [])).toBeNull()
  })

  it('builds a vertical spine model via the shared DG-1 map helper', () => {
    const model = buildStructureMapModel(
      { id: 20, title: 'Procedure', reference: 'PRO-20' },
      [
        // Procedure implements Policy (outbound toward parent)
        edge({ id: 1, src_document_id: 20, dst_document_id: 10 }),
        // SOP implements Procedure (inbound from child)
        edge({ id: 2, src_document_id: 30, dst_document_id: 20 }),
        edge({
          id: 3,
          src_document_id: 20,
          dst_document_id: 99,
          edge_type: 'related_to',
          status: 'confirmed',
        }),
      ],
      buildStructureMapLabels([
        { id: 10, title: 'Policy' },
        { id: 20, title: 'Procedure' },
        { id: 30, title: 'SOP' },
      ]),
      { orientation: STRUCTURE_MAP_DEFAULT_ORIENTATION, height: 400 },
    )
    expect(model.hubId).toBe(20)
    expect(model.nodes.map((n) => n.id).sort((a, b) => a - b)).toEqual([10, 20, 30])
    expect(model.links.map((l) => l.edgeId).sort((a, b) => a - b)).toEqual([1, 2])
    const hub = model.nodes.find((n) => n.isHub)!
    const parent = model.nodes.find((n) => n.id === 10)!
    const child = model.nodes.find((n) => n.id === 30)!
    // Vertical layout: inbound (children) above hub; outbound (parents) below.
    expect(child.y).toBeLessThan(hub.y)
    expect(parent.y).toBeGreaterThan(hub.y)
  })

  it('returns honest empty copy', () => {
    expect(structureMapEmptyCopy(false)).toMatch(/No library documents/i)
    expect(structureMapEmptyCopy(true)).toMatch(/No confirmed implements/i)
    expect(structureMapEmptyCopy(true).toLowerCase()).not.toContain('golden thread')
  })

  it('maps cascade aggregate documents onto picker refs and filters by band', () => {
    const refs = mapCascadeDocumentsToStructureRefs([
      {
        document_id: 10,
        title: 'Policy',
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
        title: 'Procedure',
        reference: 'DOC-20',
        pel_doc_ref: 'PEL-HSEQ-3001',
        cascade_level: 3,
        document_type: 'sop',
        href: '/documents/20',
        readable: true,
        parent_document_id: 10,
        parent_pel: 'PEL-HSEQ-2001',
      },
      {
        document_id: 30,
        title: 'Legacy',
        reference: 'DOC-30',
        cascade_level: null,
        href: '/documents/30',
        readable: true,
      },
    ])
    expect(refs[0].reference).toBe('PEL-HSEQ-2001')
    expect(refs[1].parentPel).toBe('PEL-HSEQ-2001')
    expect(filterStructureMapDocumentsByBand(refs, 2).map((d) => d.id)).toEqual([10])
    expect(filterStructureMapDocumentsByBand(refs, 'unset').map((d) => d.id)).toEqual([30])
    expect(filterStructureMapDocumentsByBand(refs, 'all')).toHaveLength(3)
    expect(structureMapLevelBadge(3)).toBe('L3')
    expect(structureMapBandButtonLabel({ level: 2, label: 'L2', count: 4 })).toBe('L2 (4)')
    expect(structureMapBandButtonLabel({ level: null, label: 'unset', count: 1 })).toBe(
      'Unset (1)',
    )
  })
})
