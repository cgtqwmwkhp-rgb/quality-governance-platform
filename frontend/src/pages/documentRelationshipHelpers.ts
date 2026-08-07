/**
 * Doc Graph relationship helpers (ADR-0021 Wave 1).
 *
 * Pure view-model logic for the library document Relationships tab: how an edge
 * reads from the point of view of one document, how a draft becomes a create
 * payload, and how the ambient counts are derived.
 *
 * Doc Graph is deliberately not the Golden Thread and the copy here never says
 * "golden thread": that name belongs to `ControlledDocument.library_document_id`.
 */
import type {
  CreateDocumentEdgePayload,
  DocumentEdge,
  DocumentEdgeMethod,
  DocumentEdgeType,
} from '../api/documentGraphClient'

export const DOCUMENT_EDGE_TYPES: readonly DocumentEdgeType[] = [
  'implements',
  'requires_record',
  'references',
  'related_to',
  'conflicts_with',
]

/** Peer types the API stores canonically (src id < dst id), so they read the same both ways. */
const UNDIRECTED_EDGE_TYPES: readonly DocumentEdgeType[] = ['related_to', 'conflicts_with']

export interface DocumentEdgeTypeMeta {
  /** Menu label when choosing a relationship. */
  label: string
  /** Reads "this document <outbound> the other document". */
  outbound: string
  /** Reads "this document is <inbound> the other document". */
  inbound: string
  /** One line of guidance shown under the picker. */
  helper: string
  directed: boolean
  /** True where an AI or heuristic may never author the edge, only a person. */
  humanOnly: boolean
}

export const DOCUMENT_EDGE_TYPE_META: Record<DocumentEdgeType, DocumentEdgeTypeMeta> = {
  implements: {
    label: 'Implements',
    outbound: 'Implements',
    inbound: 'Implemented by',
    helper: 'This document carries out a higher-tier document — policy → procedure → SOP.',
    directed: true,
    humanOnly: false,
  },
  requires_record: {
    label: 'Requires record',
    outbound: 'Requires record',
    inbound: 'Record required by',
    helper: 'This document obliges a form, register or record to be kept.',
    directed: true,
    humanOnly: false,
  },
  references: {
    label: 'References',
    outbound: 'References',
    inbound: 'Referenced by',
    helper: 'This document cites the other in its text.',
    directed: true,
    humanOnly: false,
  },
  related_to: {
    label: 'Related to',
    outbound: 'Related to',
    inbound: 'Related to',
    helper: 'Peer documents an operator should read together. Direction is not meaningful.',
    directed: false,
    humanOnly: false,
  },
  conflicts_with: {
    label: 'Conflicts with',
    outbound: 'Conflicts with',
    inbound: 'Conflicts with',
    helper: 'These documents contradict each other. Only a person may record a conflict.',
    directed: false,
    humanOnly: true,
  },
}

export type DocumentEdgeDirection = 'outbound' | 'inbound' | 'peer'

export interface ResolvedDocumentEdge {
  edge: DocumentEdge
  counterpartDocumentId: number
  counterpartPelDocRef: string | null
  direction: DocumentEdgeDirection
  /** How the relationship reads from the subject document. */
  relationLabel: string
}

export function isUndirectedEdgeType(edgeType: DocumentEdgeType): boolean {
  return UNDIRECTED_EDGE_TYPES.includes(edgeType)
}

/** Proposed and needs_review edges are what the confirm queue works through. */
export function isPendingDocumentEdge(edge: DocumentEdge): boolean {
  return edge.status === 'proposed' || edge.status === 'needs_review'
}

/** Rejected edges stay on record but are inert — they are not relationships. */
export function isActiveDocumentEdge(edge: DocumentEdge): boolean {
  return edge.status !== 'rejected' && !edge.deleted_at
}

/** Describe one edge from the point of view of `documentId`. */
export function resolveDocumentEdge(
  documentId: number,
  edge: DocumentEdge,
): ResolvedDocumentEdge {
  const isSource = edge.src_document_id === documentId
  const counterpartDocumentId = isSource ? edge.dst_document_id : edge.src_document_id
  const counterpartPelDocRef =
    (isSource ? edge.dst_pel_doc_ref : edge.src_pel_doc_ref) ?? null
  const meta = DOCUMENT_EDGE_TYPE_META[edge.edge_type]

  if (!meta.directed) {
    return {
      edge,
      counterpartDocumentId,
      counterpartPelDocRef,
      direction: 'peer',
      relationLabel: meta.outbound,
    }
  }

  return {
    edge,
    counterpartDocumentId,
    counterpartPelDocRef,
    direction: isSource ? 'outbound' : 'inbound',
    relationLabel: isSource ? meta.outbound : meta.inbound,
  }
}

export function resolveDocumentEdges(
  documentId: number,
  edges: DocumentEdge[],
): ResolvedDocumentEdge[] {
  return edges.map((edge) => resolveDocumentEdge(documentId, edge))
}

export interface DocumentRelationshipSummary {
  /** Active (non-rejected) edges of any direction. */
  total: number
  confirmed: number
  /** Proposed or needs_review — the confirm queue depth. */
  pending: number
  /** Confirmed edges pointing away from this document. */
  outbound: number
  /** Confirmed edges pointing at this document. */
  inbound: number
  /** Confirmed undirected peers. */
  peers: number
  /** Active conflicts at any status — these must never be hidden behind a queue. */
  conflicts: number
}

export function summariseDocumentRelationships(
  documentId: number,
  edges: DocumentEdge[],
): DocumentRelationshipSummary {
  const summary: DocumentRelationshipSummary = {
    total: 0,
    confirmed: 0,
    pending: 0,
    outbound: 0,
    inbound: 0,
    peers: 0,
    conflicts: 0,
  }

  for (const edge of edges) {
    if (!isActiveDocumentEdge(edge)) continue
    summary.total += 1
    if (edge.edge_type === 'conflicts_with') summary.conflicts += 1
    if (isPendingDocumentEdge(edge)) summary.pending += 1
    if (edge.status !== 'confirmed') continue

    summary.confirmed += 1
    const { direction } = resolveDocumentEdge(documentId, edge)
    if (direction === 'outbound') summary.outbound += 1
    else if (direction === 'inbound') summary.inbound += 1
    else summary.peers += 1
  }

  return summary
}

export interface DocumentEdgeDraft {
  /** The document whose Relationships tab is open. */
  documentId: number
  counterpartDocumentId: number
  edgeType: DocumentEdgeType
  /** Ignored for undirected types. */
  direction?: Exclude<DocumentEdgeDirection, 'peer'>
  isPrimaryParent?: boolean
  rationale?: string | null
  createdMethod?: DocumentEdgeMethod
}

/**
 * Turn an operator's draft into a create payload.
 *
 * Only a person authoring an edge by hand lands `confirmed`; every machine
 * method stays `proposed` so nothing an AI or heuristic suggested can drive
 * impact without a human confirming it (ADR-0021).
 */
export function buildDocumentEdgePayload(draft: DocumentEdgeDraft): CreateDocumentEdgePayload {
  const { documentId, counterpartDocumentId, edgeType } = draft
  if (counterpartDocumentId === documentId) {
    throw new Error('A document cannot be related to itself')
  }

  const createdMethod: DocumentEdgeMethod = draft.createdMethod ?? 'manual'
  const inbound = DOCUMENT_EDGE_TYPE_META[edgeType].directed && draft.direction === 'inbound'
  const rationale = draft.rationale?.trim()

  return {
    src_document_id: inbound ? counterpartDocumentId : documentId,
    dst_document_id: inbound ? documentId : counterpartDocumentId,
    edge_type: edgeType,
    is_primary_parent: edgeType === 'implements' ? Boolean(draft.isPrimaryParent) : false,
    status: createdMethod === 'manual' ? 'confirmed' : 'proposed',
    created_method: createdMethod,
    ...(rationale ? { rationale } : {}),
  }
}

/**
 * The live edge that already occupies this payload's slot, if any.
 *
 * The database keeps one live row per (tenant, src, dst, type) while
 * `deleted_at IS NULL`, so a *rejected* edge still holds the slot: re-proposing
 * the same pair has to unlink the old row first. Matching on `deleted_at` rather
 * than on status is what makes the tab agree with the constraint.
 */
export function findConflictingEdge(
  edges: DocumentEdge[],
  payload: CreateDocumentEdgePayload,
): DocumentEdge | null {
  const undirected = isUndirectedEdgeType(payload.edge_type)
  return (
    edges.find((edge) => {
      if (edge.deleted_at) return false
      if (edge.edge_type !== payload.edge_type) return false
      const sameOrder =
        edge.src_document_id === payload.src_document_id &&
        edge.dst_document_id === payload.dst_document_id
      const swapped =
        edge.src_document_id === payload.dst_document_id &&
        edge.dst_document_id === payload.src_document_id
      return sameOrder || (undirected && swapped)
    }) ?? null
  )
}

export type DocumentRelationshipAmbientCounts = {
  inbound: number
  outbound: number
  peers: number
}

/**
 * Ambient chips / VersionControlBar counts must not survive a listEdges failure.
 * Passing null (or hiding chips) avoids misleading zeros after an error — and
 * after a successful clear-before-fetch, zeros are honest only while loading
 * the *current* document, never another document's leftover edges.
 */
export function resolveDocumentRelationshipAmbientCounts(
  documentGraphEnabled: boolean,
  edgesError: string | null | undefined,
  summary: Pick<DocumentRelationshipSummary, 'inbound' | 'outbound' | 'peers'>,
): DocumentRelationshipAmbientCounts | null {
  if (!documentGraphEnabled || edgesError) return null
  return {
    inbound: summary.inbound,
    outbound: summary.outbound,
    peers: summary.peers,
  }
}

/** Header chips follow the same honesty rule as ambient bar counts. */
export function shouldShowDocumentRelationshipChips(
  documentGraphEnabled: boolean,
  edgesError: string | null | undefined,
): boolean {
  return Boolean(documentGraphEnabled) && !edgesError
}

/** Counterpart ids the tab still needs a title for, deduped and self excluded. */
export function counterpartDocumentIds(documentId: number, edges: DocumentEdge[]): number[] {
  const ids = new Set<number>()
  for (const edge of edges) {
    for (const id of [edge.src_document_id, edge.dst_document_id]) {
      if (id !== documentId) ids.add(id)
    }
  }
  return [...ids]
}
