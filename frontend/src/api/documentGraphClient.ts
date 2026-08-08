/**
 * Doc Graph API client (ADR-0021) — authored library document ↔ document edges.
 *
 * Doc Graph is not the Golden Thread. The Golden Thread stays
 * `ControlledDocument.library_document_id`; these edges are authored
 * relationships between two library documents and never express lifecycle
 * supersession. Every route 404s while `document_graph` is closed.
 */
import type { AxiosInstance, AxiosResponse } from 'axios'

export type DocumentEdgeType =
  | 'implements'
  | 'requires_record'
  | 'references'
  | 'related_to'
  | 'conflicts_with'

export type DocumentEdgeStatus = 'proposed' | 'confirmed' | 'rejected' | 'needs_review'

export type DocumentEdgeMethod = 'manual' | 'ai' | 'extracted' | 'heuristic' | 'auto'

export interface DocumentEdge {
  id: number
  tenant_id: number
  src_document_id: number
  dst_document_id: number
  src_pel_doc_ref?: string | null
  dst_pel_doc_ref?: string | null
  edge_type: DocumentEdgeType
  is_primary_parent: boolean
  status: DocumentEdgeStatus
  created_method: DocumentEdgeMethod
  confidence?: number | null
  rationale?: string | null
  confirmed_by_id?: number | null
  confirmed_at?: string | null
  cited_document_version_id?: number | null
  chunk_id?: number | null
  char_start?: number | null
  char_end?: number | null
  quote_hash?: string | null
  citation_text?: string | null
  cited_version?: string | null
  deleted_at?: string | null
  created_at: string
  updated_at: string
}

export interface DocumentEdgeListResponse {
  items: DocumentEdge[]
  total: number
}

export interface DocumentThreadHop {
  document_id: number
  edge_id: number
  depth: number
  direction: 'parent' | 'child'
  /** Library document title (enriched; avoids N+1). */
  title?: string | null
  /** Preferred PEL ref, else library reference_number. */
  reference?: string | null
  /** SPA deep-link, e.g. `/documents/42`. */
  href: string
  /** Hop provenance — Doc Graph threads use `graph`. */
  origin: string
  /** Edge status at walk time (`confirmed` by default ambient). */
  status: DocumentEdgeStatus | string
}

export interface DocumentThreadResponse {
  document_id: number
  ancestors: DocumentThreadHop[]
  descendants: DocumentThreadHop[]
  max_depth: number
}

export interface DocumentEdgeQuery {
  edge_type?: DocumentEdgeType
  status?: DocumentEdgeStatus
}

export interface CreateDocumentEdgePayload {
  src_document_id: number
  dst_document_id: number
  edge_type: DocumentEdgeType
  is_primary_parent?: boolean
  status?: DocumentEdgeStatus
  created_method?: DocumentEdgeMethod
  confidence?: number | null
  rationale?: string | null
}

export interface RejectDocumentEdgePayload {
  rationale?: string | null
}

export interface BulkConfirmDocumentEdgesResult {
  confirmed: DocumentEdge[]
  failed: { edge_id: number; error: unknown }[]
}

export interface HeuristicProposeResponse {
  created: DocumentEdge[]
  created_count: number
  skipped_existing: number
  skipped_unresolved: number
  sources: Record<string, number>
}

export type CitationStalenessStatus =
  | 'unchanged'
  | 'moved'
  | 'text_changed'
  | 'not_found'

export interface CitationStalenessResponse {
  edge_id: number
  status: CitationStalenessStatus
  quote_hash?: string | null
  chunk_id?: number | null
  char_start?: number | null
  char_end?: number | null
}

/** CEL tip freshness for a library document evidencing an ISO clause. */
export type ClauseDocumentFreshness = 'current' | 'stale' | 'unpinned' | 'unknown'

export interface ClauseDocumentFreshnessItem {
  document_id: number | null
  title: string | null
  evidence_link_id: number
  link_status?: string | null
  pinned_document_version_id?: number | null
  tip_document_version_id?: number | null
  tip_version_number?: string | null
  freshness: ClauseDocumentFreshness
}

export interface ClauseDocumentsResponse {
  clause_id: string
  documents: ClauseDocumentFreshnessItem[]
  total: number
}

export interface ImSeedDocumentItem {
  role: string
  document_id: number
  title: string
  created: boolean
}

export interface ImSeedEdgeItem {
  src_role: string
  dst_role: string
  edge_type: string
  edge_id: number
  created: boolean
}

/** Admin-only Incident Management Doc Graph demo seed outcome. */
export interface ImSeedResponse {
  documents: ImSeedDocumentItem[]
  edges: ImSeedEdgeItem[]
  documents_created: number
  documents_reused: number
  edges_created: number
  edges_reused: number
}

export function createDocumentGraphApi(api: AxiosInstance) {
  const base = '/api/v1/document-graph'

  const confirmEdge = (edgeId: number) =>
    api.post<DocumentEdge>(`${base}/edges/${edgeId}/confirm`)

  return {
    listEdges: (documentId: number, params?: DocumentEdgeQuery) =>
      api.get<DocumentEdgeListResponse>(`${base}/documents/${documentId}/edges`, { params }),

    getThread: (documentId: number, params?: { include_proposed?: boolean }) =>
      params
        ? api.get<DocumentThreadResponse>(
            `${base}/documents/${documentId}/thread`,
            { params },
          )
        : api.get<DocumentThreadResponse>(
            `${base}/documents/${documentId}/thread`,
          ),

    createEdge: (payload: CreateDocumentEdgePayload) =>
      api.post<DocumentEdge>(`${base}/edges`, payload),

    /**
     * Library→Map DnD propose path (DG-2). Always posts `status: proposed` so a
     * drop never auto-confirms — confirm stays on the Relationships list queue.
     */
    proposeTypedEdge: (payload: CreateDocumentEdgePayload) =>
      api.post<DocumentEdge>(`${base}/edges`, {
        ...payload,
        status: 'proposed',
      }),

    confirmEdge,

    rejectEdge: (edgeId: number, payload?: RejectDocumentEdgePayload) =>
      api.post<DocumentEdge>(`${base}/edges/${edgeId}/reject`, payload ?? {}),

    deleteEdge: (edgeId: number) => api.delete<DocumentEdge>(`${base}/edges/${edgeId}`),

    /**
     * Non-LLM heuristic / regex / vector proposals. Requires
     * `document_graph_heuristic_propose` (and master `document_graph`). Always
     * creates proposed edges only — never auto-confirms impact-driving types.
     */
    proposeHeuristics: (documentId: number) =>
      api.post<HeuristicProposeResponse>(`${base}/documents/${documentId}/propose`),

    getCitationStaleness: (edgeId: number) =>
      api.get<CitationStalenessResponse>(`${base}/edges/${edgeId}/citation-staleness`),

    /**
     * ISO reverse: library documents evidencing a clause, with CEL tip freshness.
     * Requires master `document_graph` (404 when closed).
     */
    listClauseDocuments: (clauseId: string) =>
      api.get<ClauseDocumentsResponse>(
        `${base}/clauses/${encodeURIComponent(clauseId)}/documents`,
      ),

    /**
     * Admin-only Incident Management demo vertical seed. Requires master
     * `document_graph` (404 when closed) and `admin:manage`.
     */
    seedIncidentManagementVertical: () =>
      api.post<ImSeedResponse>(`${base}/demo/incident-management/seed`),

    /**
     * Confirm a queue of edges one at a time and report per-edge outcomes.
     *
     * There is no bulk confirm route yet, and a partial failure must stay
     * visible: an edge another reviewer rejected in the meantime is refused by
     * the API, and swallowing that would tell the operator they confirmed
     * something they did not.
     */
    confirmEdges: async (edgeIds: number[]): Promise<BulkConfirmDocumentEdgesResult> => {
      const confirmed: DocumentEdge[] = []
      const failed: { edge_id: number; error: unknown }[] = []
      for (const edgeId of edgeIds) {
        try {
          const response: AxiosResponse<DocumentEdge> = await confirmEdge(edgeId)
          confirmed.push(response.data)
        } catch (error) {
          failed.push({ edge_id: edgeId, error })
        }
      }
      return { confirmed, failed }
    },
  }
}

export type DocumentGraphApi = ReturnType<typeof createDocumentGraphApi>
