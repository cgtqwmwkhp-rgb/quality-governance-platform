import { describe, expect, it } from 'vitest'
import type { DocumentEdge, DocumentThreadResponse } from '../../api/documentGraphClient'
import type { CampaignComplianceRow } from '../../api/documentCampaignClient'
import type { KnowledgeEvidenceLink, RegulatoryImpact } from '../../api/knowledgeBankClient'
import {
  buildPublishImpactPreview,
  campaignsAffectedByPublish,
  dependentDocumentIds,
  evidenceLikelyNeedsReview,
  openImpactsForDocument,
} from '../documentPublishImpactHelpers'

function edge(overrides: Partial<DocumentEdge> & { id: number }): DocumentEdge {
  return {
    tenant_id: 1,
    src_document_id: 20,
    dst_document_id: 10,
    edge_type: 'implements',
    is_primary_parent: false,
    status: 'confirmed',
    created_method: 'manual',
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

describe('documentPublishImpactHelpers', () => {
  it('lists confirmed evidence as rematch candidates', () => {
    const evidence = [
      { id: 1, clause_id: '4.1', status: 'confirmed', title: 'Context' },
      { id: 2, clause_id: '4.2', status: 'proposed', title: 'Needs' },
    ] as KnowledgeEvidenceLink[]
    expect(evidenceLikelyNeedsReview(evidence).map((e) => e.id)).toEqual([1])
  })

  it('filters campaigns for the subject document', () => {
    const rows = [
      { campaign_id: 1, document_id: 10, status: 'active', assigned: 5, pending: 2 },
      { campaign_id: 2, document_id: 99, status: 'active', assigned: 1, pending: 0 },
      { campaign_id: 3, document_id: 10, status: 'closed', assigned: 5, pending: 0 },
    ] as CampaignComplianceRow[]
    expect(campaignsAffectedByPublish(10, rows).map((r) => r.campaign_id)).toEqual([1])
  })

  it('collects dependents from thread descendants and inbound implements', () => {
    const thread: DocumentThreadResponse = {
      document_id: 10,
      max_depth: 4,
      ancestors: [],
      descendants: [
        { document_id: 30, edge_id: 1, depth: 1, direction: 'child' },
        { document_id: 10, edge_id: 2, depth: 0, direction: 'child' },
      ],
    }
    const ids = dependentDocumentIds(10, [edge({ id: 9 })], thread)
    expect(ids).toEqual([20, 30])
  })

  it('ignores closed regulatory impacts', () => {
    const impacts = [
      { id: 1, update_id: 'U1', document_id: 10, status: 'open' },
      { id: 2, update_id: 'U2', document_id: 10, status: 'closed' },
      { id: 3, update_id: 'U3', document_id: null, status: 'open' },
    ] as RegulatoryImpact[]
    expect(openImpactsForDocument(10, impacts).map((i) => i.id)).toEqual([1])
  })

  it('builds a preview with lifecycle steps always present', () => {
    const preview = buildPublishImpactPreview({
      documentId: 10,
      edges: [edge({ id: 9 })],
      thread: null,
      evidence: [{ id: 1, clause_id: '4.1', status: 'confirmed' } as KnowledgeEvidenceLink],
      campaigns: [],
      impacts: [],
      quizCount: 1,
    })
    expect(preview.empty).toBe(false)
    expect(preview.sections.find((s) => s.id === 'dependents')?.items).toHaveLength(1)
    expect(preview.sections.find((s) => s.id === 'evidence')?.items).toHaveLength(1)
    const lifecycle = preview.sections.find((s) => s.id === 'lifecycle')
    expect(lifecycle?.items.some((i) => i.id === 'life-quiz-stale')).toBe(true)
  })

  it('marks empty when no graph/campaign/evidence/impact rows', () => {
    const preview = buildPublishImpactPreview({
      documentId: 10,
      edges: [],
      thread: null,
      evidence: [],
      campaigns: [],
      impacts: [],
    })
    expect(preview.empty).toBe(true)
    expect(preview.sections.find((s) => s.id === 'lifecycle')?.items.length).toBeGreaterThan(0)
  })
})
