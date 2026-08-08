/**
 * Library → Relationships Map DnD propose helpers (DG-2).
 *
 * Drag a library document onto the map hub to create a *proposed* typed edge.
 * Never auto-confirms — confirm stays on the list queue (ADR-0021).
 * Deep-links for counterparts continue to use hop `href` from the API / X-1
 * registry; this module does not invent parallel URL builders.
 */
import type {
  CreateDocumentEdgePayload,
  DocumentEdge,
  DocumentEdgeType,
} from '../../api/documentGraphClient'
import {
  DOCUMENT_EDGE_TYPE_META,
  findConflictingEdge,
} from '../../pages/documentRelationshipHelpers'

/** HTML5 MIME for library-document drags (Documents tray + Relationships tray). */
export const LIBRARY_DOCUMENT_DRAG_MIME = 'application/x-qgp-library-document'

export const DND_PROPOSE_RATIONALE = 'Proposed via drag-and-drop from Library tray'

export interface LibraryDocumentDragPayload {
  documentId: number
  title?: string
  reference?: string | null
}

export type DndProposeDropResult =
  | { ok: true; payload: CreateDocumentEdgePayload }
  | { ok: false; reason: string }

/**
 * Spine / obligation drops treat the dragged document as the child (src) and
 * the hub as the parent (dst) — matching the v4 Relationships canvas.
 * Peer / citation / conflict types point hub → dragged (or canonicalize).
 */
export function dndProposeDirection(
  edgeType: DocumentEdgeType,
): 'inbound' | 'outbound' {
  if (edgeType === 'implements' || edgeType === 'requires_record') {
    return 'inbound'
  }
  return 'outbound'
}

export function shouldEnableLibraryDocumentDrag(dndProposeEnabled: boolean): boolean {
  return Boolean(dndProposeEnabled)
}

/** Map drop UI needs the DnD programme flag (map toggle is separate). */
export function shouldEnableRelationshipsMapDnd(dndProposeEnabled: boolean): boolean {
  return Boolean(dndProposeEnabled)
}

export function serializeLibraryDocumentDrag(payload: LibraryDocumentDragPayload): string {
  if (!Number.isFinite(payload.documentId) || payload.documentId <= 0) {
    throw new Error('Library document drag requires a positive documentId')
  }
  return JSON.stringify({
    documentId: payload.documentId,
    ...(payload.title ? { title: payload.title } : {}),
    ...(payload.reference != null && payload.reference !== ''
      ? { reference: payload.reference }
      : {}),
  })
}

export function parseLibraryDocumentDragData(raw: string | null | undefined): LibraryDocumentDragPayload | null {
  if (!raw?.trim()) return null
  try {
    const parsed = JSON.parse(raw) as Partial<LibraryDocumentDragPayload>
    const documentId = Number(parsed.documentId)
    if (!Number.isFinite(documentId) || documentId <= 0) return null
    return {
      documentId,
      ...(typeof parsed.title === 'string' ? { title: parsed.title } : {}),
      ...(parsed.reference === null || typeof parsed.reference === 'string'
        ? { reference: parsed.reference }
        : {}),
    }
  } catch {
    return null
  }
}

/**
 * Read a library-document drag from a DataTransfer, preferring the custom MIME
 * and falling back to plain text (some browsers strip custom types on drop).
 */
export function parseLibraryDocumentDrag(
  dataTransfer: DataTransfer | null | undefined,
): LibraryDocumentDragPayload | null {
  if (!dataTransfer) return null
  const custom = parseLibraryDocumentDragData(dataTransfer.getData(LIBRARY_DOCUMENT_DRAG_MIME))
  if (custom) return custom
  return parseLibraryDocumentDragData(dataTransfer.getData('text/plain'))
}

export function setLibraryDocumentDragData(
  dataTransfer: DataTransfer,
  payload: LibraryDocumentDragPayload,
): void {
  const serialized = serializeLibraryDocumentDrag(payload)
  dataTransfer.setData(LIBRARY_DOCUMENT_DRAG_MIME, serialized)
  dataTransfer.setData('text/plain', serialized)
  dataTransfer.effectAllowed = 'copy'
}

/**
 * Build a create payload that is always proposed.
 *
 * Uses `created_method: manual` (a person dragged it) but forces `proposed` so
 * DnD never short-circuits the confirm queue — unlike the hand-author form.
 */
export function buildDndProposeEdgePayload(input: {
  hubDocumentId: number
  draggedDocumentId: number
  edgeType: DocumentEdgeType
  rationale?: string | null
}): CreateDocumentEdgePayload {
  const { hubDocumentId, draggedDocumentId, edgeType } = input
  if (draggedDocumentId === hubDocumentId) {
    throw new Error('A document cannot be related to itself')
  }

  const inbound =
    DOCUMENT_EDGE_TYPE_META[edgeType].directed &&
    dndProposeDirection(edgeType) === 'inbound'

  const src = inbound ? draggedDocumentId : hubDocumentId
  const dst = inbound ? hubDocumentId : draggedDocumentId
  const rationale = (input.rationale ?? DND_PROPOSE_RATIONALE).trim()

  return {
    src_document_id: src,
    dst_document_id: dst,
    edge_type: edgeType,
    is_primary_parent: false,
    status: 'proposed',
    created_method: 'manual',
    ...(rationale ? { rationale } : {}),
  }
}

export function resolveDndProposeDrop(input: {
  hubDocumentId: number
  dragged: LibraryDocumentDragPayload | null
  edgeType: DocumentEdgeType
  existingEdges: DocumentEdge[]
}): DndProposeDropResult {
  if (!input.dragged) {
    return { ok: false, reason: 'Drop a library document onto the hub to propose a relationship.' }
  }
  if (input.dragged.documentId === input.hubDocumentId) {
    return { ok: false, reason: 'Drop a different library document onto the hub to propose.' }
  }

  let payload: CreateDocumentEdgePayload
  try {
    payload = buildDndProposeEdgePayload({
      hubDocumentId: input.hubDocumentId,
      draggedDocumentId: input.dragged.documentId,
      edgeType: input.edgeType,
    })
  } catch (err) {
    return {
      ok: false,
      reason: err instanceof Error ? err.message : 'Could not build propose payload',
    }
  }

  const conflict = findConflictingEdge(input.existingEdges, payload)
  if (conflict) {
    return {
      ok: false,
      reason: 'A relationship of this type already exists between these documents.',
    }
  }

  return { ok: true, payload }
}
