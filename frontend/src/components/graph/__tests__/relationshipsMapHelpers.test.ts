import { describe, expect, it } from 'vitest'
import type { DocumentEdge } from '../../../api/documentGraphClient'
import {
  buildRelationshipMapModel,
  relationshipMapEdgeCaption,
  resolveRelationshipsPanelView,
  shouldShowRelationshipsMapToggle,
} from '../relationshipsMapHelpers'

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

describe('relationshipsMapHelpers', () => {
  it('hides the Map|List toggle when the map flag is off', () => {
    expect(shouldShowRelationshipsMapToggle(false)).toBe(false)
    expect(shouldShowRelationshipsMapToggle(true)).toBe(true)
  })

  it('forces list view when the map flag is off even if map is preferred', () => {
    expect(resolveRelationshipsPanelView(false, 'map')).toBe('list')
    expect(resolveRelationshipsPanelView(true, 'map')).toBe('map')
    expect(resolveRelationshipsPanelView(true, 'list')).toBe('list')
  })

  it('builds a hub-and-peers model from confirmed edges only', () => {
    const model = buildRelationshipMapModel(
      10,
      'Incident Management Policy',
      'POL-10',
      [
        edge({ id: 1, dst_document_id: 20, dst_pel_doc_ref: 'SOP-20' }),
        edge({
          id: 2,
          src_document_id: 30,
          dst_document_id: 10,
          edge_type: 'requires_record',
          status: 'proposed',
        }),
        edge({
          id: 3,
          src_document_id: 10,
          dst_document_id: 40,
          edge_type: 'related_to',
          status: 'confirmed',
        }),
      ],
      { 20: 'Reporting SOP', 40: 'Related guidance' },
      { width: 400, height: 300, radius: 100 },
    )

    expect(model.hubId).toBe(10)
    expect(model.nodes[0]).toMatchObject({
      id: 10,
      isHub: true,
      x: 200,
      y: 150,
      label: 'Incident Management Policy',
    })
    expect(model.nodes.map((n) => n.id).sort((a, b) => a - b)).toEqual([10, 20, 40])
    expect(model.links.map((l) => l.edgeId).sort((a, b) => a - b)).toEqual([1, 3])
    expect(model.nodes.find((n) => n.id === 20)?.label).toBe('Reporting SOP')
    expect(relationshipMapEdgeCaption('implements')).toBe('Implements')
  })

  it('places a single peer above the hub', () => {
    const model = buildRelationshipMapModel(
      10,
      'Hub',
      null,
      [edge({ id: 1 })],
      { 20: 'Peer' },
      { width: 400, height: 300, radius: 100 },
    )
    const peer = model.nodes.find((n) => n.id === 20)
    expect(peer?.x).toBeCloseTo(200, 5)
    expect(peer?.y).toBeCloseTo(50, 5)
  })
})
