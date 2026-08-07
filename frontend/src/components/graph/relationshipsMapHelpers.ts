/**
 * Pure helpers for the Relationships Map|List view (DG-1).
 *
 * Hub-and-peers layout over existing edges — no force-directed layout.
 * Never calls Doc Graph the Golden Thread.
 */
import type { DocumentEdge } from '../../api/documentGraphClient'
import {
  DOCUMENT_EDGE_TYPE_META,
  isActiveDocumentEdge,
  resolveDocumentEdge,
  type DocumentEdgeDirection,
} from '../../pages/documentRelationshipHelpers'

export type RelationshipsPanelViewMode = 'list' | 'map'

export interface RelationshipMapNode {
  id: number
  label: string
  reference: string | null
  href: string
  relationLabel: string | null
  direction: DocumentEdgeDirection | 'hub'
  status: string | null
  isHub: boolean
  x: number
  y: number
}

export interface RelationshipMapLink {
  edgeId: number
  fromId: number
  toId: number
  edgeType: string
  status: string
}

export interface RelationshipMapModel {
  nodes: RelationshipMapNode[]
  links: RelationshipMapLink[]
  width: number
  height: number
  hubId: number
}

export function shouldShowRelationshipsMapToggle(mapViewEnabled: boolean): boolean {
  return Boolean(mapViewEnabled)
}

export function resolveRelationshipsPanelView(
  mapViewEnabled: boolean,
  preferred: RelationshipsPanelViewMode,
): RelationshipsPanelViewMode {
  if (!mapViewEnabled) return 'list'
  return preferred === 'map' ? 'map' : 'list'
}

function peerLabel(
  counterpartId: number,
  pelRef: string | null,
  labels: Record<number, string | null | undefined>,
): string {
  const known = labels[counterpartId]
  if (typeof known === 'string' && known.trim()) return known.trim()
  if (counterpartId in labels && (known === null || known === undefined)) {
    return pelRef ? `${pelRef} — not available to you` : `Document #${counterpartId} — not available to you`
  }
  return pelRef ?? `Document #${counterpartId}`
}

/**
 * Place the subject document at the hub and arrange counterparts on a circle.
 * Confirmed, non-deleted edges only — proposed links stay in the List confirm queue.
 */
export function buildRelationshipMapModel(
  documentId: number,
  documentTitle: string,
  documentReference: string | null | undefined,
  edges: DocumentEdge[],
  labels: Record<number, string | null | undefined> = {},
  options?: { width?: number; height?: number; radius?: number },
): RelationshipMapModel {
  const width = options?.width ?? 560
  const height = options?.height ?? 360
  const radius = options?.radius ?? Math.min(width, height) * 0.34
  const cx = width / 2
  const cy = height / 2

  const confirmed = edges.filter(
    (edge) => isActiveDocumentEdge(edge) && edge.status === 'confirmed',
  )

  const peerById = new Map<
    number,
    {
      label: string
      reference: string | null
      relationLabel: string
      direction: DocumentEdgeDirection
      status: string
    }
  >()
  const links: RelationshipMapLink[] = []

  for (const edge of confirmed) {
    const resolved = resolveDocumentEdge(documentId, edge)
    const counterpartId = resolved.counterpartDocumentId
    if (counterpartId === documentId) continue

    if (!peerById.has(counterpartId)) {
      peerById.set(counterpartId, {
        label: peerLabel(counterpartId, resolved.counterpartPelDocRef, labels),
        reference: resolved.counterpartPelDocRef,
        relationLabel: resolved.relationLabel,
        direction: resolved.direction,
        status: edge.status,
      })
    }

    const fromId = edge.src_document_id
    const toId = edge.dst_document_id
    links.push({
      edgeId: edge.id,
      fromId,
      toId,
      edgeType: edge.edge_type,
      status: edge.status,
    })
  }

  const peers = [...peerById.entries()]
  const nodes: RelationshipMapNode[] = [
    {
      id: documentId,
      label: documentTitle.trim() || `Document #${documentId}`,
      reference: documentReference?.trim() || null,
      href: `/documents/${documentId}`,
      relationLabel: null,
      direction: 'hub',
      status: null,
      isHub: true,
      x: cx,
      y: cy,
    },
  ]

  peers.forEach(([id, peer], index) => {
    const angle = peers.length === 1 ? -Math.PI / 2 : (2 * Math.PI * index) / peers.length - Math.PI / 2
    nodes.push({
      id,
      label: peer.label,
      reference: peer.reference,
      href: `/documents/${id}`,
      relationLabel: peer.relationLabel,
      direction: peer.direction,
      status: peer.status,
      isHub: false,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    })
  })

  return { nodes, links, width, height, hubId: documentId }
}

export function relationshipMapEdgeCaption(edgeType: string): string {
  const meta = DOCUMENT_EDGE_TYPE_META[edgeType as keyof typeof DOCUMENT_EDGE_TYPE_META]
  return meta?.label ?? edgeType
}
