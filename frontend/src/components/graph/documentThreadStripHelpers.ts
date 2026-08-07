/**
 * Pure helpers for the ambient Doc Graph implements thread strip (DG-1).
 *
 * Consumes enriched `/thread` hops from X-0. Never calls Doc Graph the Golden Thread.
 */
import type { DocumentThreadHop, DocumentThreadResponse } from '../../api/documentGraphClient'

export interface ThreadStripCurrentDocument {
  documentId: number
  title: string
  reference?: string | null
}

export interface ThreadStripItem {
  key: string
  kind: 'hop' | 'current'
  documentId: number
  title: string
  reference: string | null
  href: string
  depth?: number
  direction?: 'parent' | 'child'
  status?: string
  origin?: string
}

/** Ambient strip only mounts when the programme flag is open (defaults off). */
export function shouldShowDocumentThreadStrip(threadAmbientEnabled: boolean): boolean {
  return Boolean(threadAmbientEnabled)
}

/** Master Doc Graph must also be open — thread routes 404 when closed. */
export function shouldFetchDocumentThread(
  documentGraphEnabled: boolean,
  threadAmbientEnabled: boolean,
): boolean {
  return Boolean(documentGraphEnabled) && Boolean(threadAmbientEnabled)
}

export function hopDisplayTitle(hop: Pick<DocumentThreadHop, 'title' | 'reference' | 'document_id'>): string {
  const title = hop.title?.trim()
  if (title) return title
  const reference = hop.reference?.trim()
  if (reference) return reference
  return `Document #${hop.document_id}`
}

/**
 * Breadcrumb order: deepest ancestor (root) → … → parent → current → children by depth.
 *
 * Ancestors from the API are typically nearest-first; we sort by depth descending so the
 * strip reads as the governed implements spine from root down.
 */
export function buildThreadStripItems(
  thread: DocumentThreadResponse | null | undefined,
  current: ThreadStripCurrentDocument,
): ThreadStripItem[] {
  const ancestors = [...(thread?.ancestors ?? [])].sort((a, b) => b.depth - a.depth)
  const descendants = [...(thread?.descendants ?? [])].sort((a, b) => {
    if (a.depth !== b.depth) return a.depth - b.depth
    return a.document_id - b.document_id
  })

  const items: ThreadStripItem[] = []

  for (const hop of ancestors) {
    items.push({
      key: `ancestor-${hop.edge_id}-${hop.document_id}`,
      kind: 'hop',
      documentId: hop.document_id,
      title: hopDisplayTitle(hop),
      reference: hop.reference?.trim() || null,
      href: hop.href || `/documents/${hop.document_id}`,
      depth: hop.depth,
      direction: hop.direction,
      status: hop.status,
      origin: hop.origin,
    })
  }

  items.push({
    key: `current-${current.documentId}`,
    kind: 'current',
    documentId: current.documentId,
    title: current.title.trim() || `Document #${current.documentId}`,
    reference: current.reference?.trim() || null,
    href: `/documents/${current.documentId}`,
  })

  for (const hop of descendants) {
    items.push({
      key: `descendant-${hop.edge_id}-${hop.document_id}`,
      kind: 'hop',
      documentId: hop.document_id,
      title: hopDisplayTitle(hop),
      reference: hop.reference?.trim() || null,
      href: hop.href || `/documents/${hop.document_id}`,
      depth: hop.depth,
      direction: hop.direction,
      status: hop.status,
      origin: hop.origin,
    })
  }

  return items
}

/** True when there is at least one hop beyond the current document. */
export function threadStripHasNeighbors(items: ThreadStripItem[]): boolean {
  return items.some((item) => item.kind === 'hop')
}
