/**
 * Publish / revise impact preview helpers (Doc Graph Wave 1 PR-D).
 *
 * Read-only checklist of likely side effects before library publish.
 * Durable Doc Graph impact jobs remain Wave 2; this surface is honesty for
 * rematch / campaigns / dependents already wired on publish.
 *
 * Never calls Doc Graph the Golden Thread.
 */
import type { DocumentEdge, DocumentThreadResponse } from '../api/documentGraphClient'
import type { CampaignComplianceRow } from '../api/documentCampaignClient'
import type { KnowledgeEvidenceLink, RegulatoryImpact } from '../api/knowledgeBankClient'
import { isActiveDocumentEdge, resolveDocumentEdges } from './documentRelationshipHelpers'

export interface PublishImpactPreviewItem {
  id: string
  label: string
  detail?: string
}

export interface PublishImpactPreviewSection {
  id: 'dependents' | 'evidence' | 'campaigns' | 'impacts' | 'lifecycle'
  title: string
  description: string
  items: PublishImpactPreviewItem[]
}

export interface PublishImpactPreview {
  sections: PublishImpactPreviewSection[]
  totalItems: number
  empty: boolean
}

export interface BuildPublishImpactPreviewInput {
  documentId: number
  edges: DocumentEdge[]
  thread: DocumentThreadResponse | null
  evidence: KnowledgeEvidenceLink[]
  campaigns: CampaignComplianceRow[]
  impacts: RegulatoryImpact[]
  quizCount?: number
}

/** Confirmed evidence rematch may move to needs_review on publish. */
export function evidenceLikelyNeedsReview(
  evidence: KnowledgeEvidenceLink[],
): KnowledgeEvidenceLink[] {
  return evidence.filter((link) => link.status === 'confirmed')
}

/** Active / launched campaigns for this library document that may receive re-ack. */
export function campaignsAffectedByPublish(
  documentId: number,
  campaigns: CampaignComplianceRow[],
): CampaignComplianceRow[] {
  return campaigns.filter(
    (row) =>
      row.document_id === documentId &&
      ['active', 'launched', 'draft', 'scheduled'].includes(String(row.status).toLowerCase()),
  )
}

/** Open (non-closed) regulatory watch impacts still linked to this document. */
export function openImpactsForDocument(
  documentId: number,
  impacts: RegulatoryImpact[],
): RegulatoryImpact[] {
  return impacts.filter((impact) => {
    if (impact.document_id == null || impact.document_id !== documentId) return false
    const status = String(impact.status || '').toLowerCase()
    return status !== 'closed' && status !== 'dismissed' && status !== 'resolved'
  })
}

/**
 * Downstream dependents: thread descendants plus confirmed inbound implements
 * (documents that carry out this one).
 */
export function dependentDocumentIds(
  documentId: number,
  edges: DocumentEdge[],
  thread: DocumentThreadResponse | null,
): number[] {
  const ids = new Set<number>()
  for (const hop of thread?.descendants ?? []) {
    if (hop.document_id !== documentId) ids.add(hop.document_id)
  }
  for (const resolved of resolveDocumentEdges(documentId, edges)) {
    if (!isActiveDocumentEdge(resolved.edge)) continue
    if (resolved.edge.status !== 'confirmed') continue
    if (resolved.direction === 'inbound' && resolved.edge.edge_type === 'implements') {
      ids.add(resolved.counterpartDocumentId)
    }
  }
  return [...ids].sort((a, b) => a - b)
}

export function buildPublishImpactPreview(
  input: BuildPublishImpactPreviewInput,
): PublishImpactPreview {
  const dependents = dependentDocumentIds(input.documentId, input.edges, input.thread)
  const rematch = evidenceLikelyNeedsReview(input.evidence)
  const campaigns = campaignsAffectedByPublish(input.documentId, input.campaigns)
  const impacts = openImpactsForDocument(input.documentId, input.impacts)
  const quizCount = input.quizCount ?? 0

  const sections: PublishImpactPreviewSection[] = [
    {
      id: 'dependents',
      title: 'Downstream document relationships',
      description:
        'Library documents that implement this one, or sit below it on the Doc Graph thread.',
      items: dependents.map((id) => ({
        id: `dep-${id}`,
        label: `Document #${id}`,
        detail: 'May need review after this version publishes',
      })),
    },
    {
      id: 'evidence',
      title: 'Clause evidence rematch',
      description:
        'Confirmed clause evidence links may move to needs_review when rematch runs on publish.',
      items: rematch.map((link) => ({
        id: `ev-${link.id}`,
        label: link.clause_id,
        detail: link.title ?? link.scheme ?? undefined,
      })),
    },
    {
      id: 'campaigns',
      title: 'Reading campaigns',
      description:
        'Active or draft campaigns for this document may spawn a re-acknowledgement campaign.',
      items: campaigns.map((row) => ({
        id: `camp-${row.campaign_id}`,
        label: row.title || row.document_title || `Campaign #${row.campaign_id}`,
        detail: `${row.status} · ${row.pending} pending of ${row.assigned} assigned`,
      })),
    },
    {
      id: 'impacts',
      title: 'Open regulatory watch impacts',
      description: 'Open impacts stay linked; publish does not close them automatically.',
      items: impacts.map((impact) => ({
        id: `imp-${impact.id}`,
        label: `Update ${impact.update_id}`,
        detail: impact.status,
      })),
    },
    {
      id: 'lifecycle',
      title: 'Governed knowledge lifecycle',
      description:
        'Publish runs rematch / quiz stale / quiz draft hooks when content is present (ADR-0021 P0).',
      items: [
        {
          id: 'life-rematch',
          label: 'Rematch clause evidence for the new version',
        },
        ...(quizCount > 0
          ? [
              {
                id: 'life-quiz-stale',
                label: `Mark ${quizCount} existing quiz draft(s) stale`,
              },
            ]
          : []),
        {
          id: 'life-quiz-draft',
          label: 'Generate a quiz draft candidate for the published version',
        },
      ],
    },
  ]

  const totalItems = sections.reduce((sum, section) => sum + section.items.length, 0)
  return {
    sections,
    totalItems,
    empty: dependents.length === 0 && rematch.length === 0 && campaigns.length === 0 && impacts.length === 0,
  }
}
