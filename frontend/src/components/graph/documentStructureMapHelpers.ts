/**
 * Pure helpers for the whole-library Structure map (DG-3).
 *
 * Explores confirmed `implements` edges across the library using the DG-1 map
 * model. Never calls Doc Graph the Golden Thread. Never invents ISO %.
 */
import type { DocumentEdge } from '../../api/documentGraphClient'
import { isActiveDocumentEdge } from '../../pages/documentRelationshipHelpers'
import {
  buildRelationshipMapModel,
  type RelationshipMapModel,
} from './relationshipsMapHelpers'
import {
  DEFAULT_GRAPH_ORIENTATION,
  resolveGraphOrientation,
  type GraphOrientation,
} from './graphOrientation'

/** Structure map prefers vertical spine (was "spine explorer"). */
export const STRUCTURE_MAP_DEFAULT_ORIENTATION: GraphOrientation = 'vertical'

export interface StructureMapDocumentRef {
  id: number
  title: string
  reference?: string | null
  documentType?: string | null
}

/**
 * Page/chrome mounts only when the programme Structure map flag is open.
 * Master Doc Graph is checked separately before fetches (404s when closed).
 */
export function shouldShowDocumentStructureMap(structureMapEnabled: boolean): boolean {
  return Boolean(structureMapEnabled)
}

/** Fetch only when master Doc Graph and Structure map flags are both open. */
export function shouldFetchDocumentStructureMap(
  documentGraphEnabled: boolean,
  structureMapEnabled: boolean,
): boolean {
  return Boolean(documentGraphEnabled) && Boolean(structureMapEnabled)
}

/** Confirmed, live implements edges only — proposed stay out of the Structure map. */
export function filterConfirmedImplementsEdges(edges: DocumentEdge[]): DocumentEdge[] {
  return edges.filter(
    (edge) =>
      isActiveDocumentEdge(edge) &&
      edge.status === 'confirmed' &&
      edge.edge_type === 'implements',
  )
}

/** Deduplicate by edge id (library-wide scan hits both endpoints of each edge). */
export function dedupeDocumentEdgesById(edges: DocumentEdge[]): DocumentEdge[] {
  const byId = new Map<number, DocumentEdge>()
  for (const edge of edges) {
    if (!byId.has(edge.id)) byId.set(edge.id, edge)
  }
  return [...byId.values()].sort((a, b) => a.id - b.id)
}

/**
 * Documents that appear as implements parents (dst) but never as implements
 * children (src) among the confirmed set — forest roots for library overview.
 */
export function findStructureMapRootIds(edges: DocumentEdge[]): number[] {
  const confirmed = filterConfirmedImplementsEdges(edges)
  const children = new Set(confirmed.map((edge) => edge.src_document_id))
  const parents = new Set(confirmed.map((edge) => edge.dst_document_id))
  const roots = [...parents].filter((id) => !children.has(id))
  return roots.sort((a, b) => a - b)
}

export function resolveStructureMapFocusId(
  preferred: number | null | undefined,
  documents: StructureMapDocumentRef[],
  rootIds: number[] = [],
): number | null {
  if (
    preferred != null &&
    Number.isFinite(preferred) &&
    documents.some((doc) => doc.id === preferred)
  ) {
    return preferred
  }
  for (const rootId of rootIds) {
    if (documents.some((doc) => doc.id === rootId)) return rootId
  }
  return documents[0]?.id ?? null
}

export function buildStructureMapLabels(
  documents: StructureMapDocumentRef[],
): Record<number, string | null | undefined> {
  const labels: Record<number, string | null | undefined> = {}
  for (const doc of documents) {
    labels[doc.id] = doc.title.trim() || null
  }
  return labels
}

/**
 * Hub-and-peers (or vertical spine) model for one focus document over confirmed
 * implements edges — reuses DG-1 `buildRelationshipMapModel`.
 */
export function buildStructureMapModel(
  focus: StructureMapDocumentRef,
  edges: DocumentEdge[],
  labels: Record<number, string | null | undefined> = {},
  options?: {
    width?: number
    height?: number
    orientation?: GraphOrientation
  },
): RelationshipMapModel {
  const orientation = resolveGraphOrientation(
    options?.orientation,
    STRUCTURE_MAP_DEFAULT_ORIENTATION,
  )
  const implementsEdges = filterConfirmedImplementsEdges(edges)
  return buildRelationshipMapModel(
    focus.id,
    focus.title,
    focus.reference,
    implementsEdges,
    labels,
    {
      width: options?.width,
      height: options?.height,
      orientation,
    },
  )
}

export function structureMapEmptyCopy(hasLibraryDocuments: boolean): string {
  if (!hasLibraryDocuments) {
    return 'No library documents available to explore yet.'
  }
  return 'No confirmed implements relationships for this focus document yet. Propose and confirm edges from Document Relationships — Structure map never invents a spine.'
}

export { DEFAULT_GRAPH_ORIENTATION, resolveGraphOrientation }
