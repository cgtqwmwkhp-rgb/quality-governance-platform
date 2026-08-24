/**
 * Pure helpers for the Doc Graph slice of the Knowledge Exceptions inbox (WE-1).
 *
 * Doc Graph proposals are reviewed on the existing Exceptions page — there is no
 * second Confirm Queue route (ADR-0023) and nothing is copied into CEL. Evidence
 * links stay the CEL source of truth; `document_edges` stays the graph's.
 */
import { DOCUMENT_EDGE_TYPE_META } from './documentRelationshipHelpers'
import type {
  DocumentEdgeType,
  PendingDocumentEdgeEndpoint,
  PendingDocumentEdgeItem,
} from '../api/documentGraphClient'

/** How a queued endpoint is named, without inventing a title the ACL withheld. */
export function pendingEndpointLabel(endpoint: PendingDocumentEdgeEndpoint): string {
  const title = endpoint.title?.trim()
  if (endpoint.readable && title) return title
  const reference = endpoint.reference?.trim()
  if (endpoint.readable && reference) return reference
  return `Document #${endpoint.document_id} — not available to you`
}

/** Directed relationship sentence, e.g. "Implements" / "Related to". */
export function pendingEdgeRelationLabel(edgeType: DocumentEdgeType): string {
  return DOCUMENT_EDGE_TYPE_META[edgeType]?.label ?? edgeType
}

export function pendingEdgeHelper(edgeType: DocumentEdgeType): string {
  return DOCUMENT_EDGE_TYPE_META[edgeType]?.helper ?? ''
}

/**
 * True when both ends are unreadable, so confirming would be a blind decision.
 * The row is shown either way — hiding it would understate the queue — but the
 * page must not offer confirm on a relationship the operator cannot see.
 */
export function isBlindPendingEdge(item: PendingDocumentEdgeItem): boolean {
  return !item.src.readable && !item.dst.readable
}

export interface GraphQueueHonesty {
  /** Count copy for the queue header. */
  summary: string
  /** True when the API cut the page, so the count is not a global total. */
  truncated: boolean
}

export function buildGraphQueueHonesty(page: {
  returned: number
  limit: number
  truncated: boolean
}): GraphQueueHonesty {
  const noun = page.returned === 1 ? 'proposed relationship' : 'proposed relationships'
  const base = `${page.returned} ${noun} awaiting confirmation`
  if (!page.truncated) {
    return {
      summary: `${base} (page of up to ${page.limit} — not a global total)`,
      truncated: false,
    }
  }
  return {
    summary: `${base} — more than ${page.limit} are pending; this page is cut at ${page.limit}`,
    truncated: true,
  }
}

/**
 * A 404 from the queue means Doc Graph is closed on the server, which is not the
 * same claim as "nothing is pending". Callers must say which one it is.
 */
export function isGraphQueueClosedError(error: unknown): boolean {
  const status = (error as { response?: { status?: number } } | null)?.response?.status
  return status === 404
}
