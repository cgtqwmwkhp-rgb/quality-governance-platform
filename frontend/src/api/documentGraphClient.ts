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

export function createDocumentGraphApi(api: AxiosInstance) {
  const base = '/api/v1/document-graph'

  const confirmEdge = (edgeId: number) =>
    api.post<DocumentEdge>(`${base}/edges/${edgeId}/confirm`)

  return {
    listEdges: (documentId: number, params?: DocumentEdgeQuery) =>
      api.get<DocumentEdgeListResponse>(`${base}/documents/${documentId}/edges`, { params }),

    getThread: (documentId: number) =>
      api.get<DocumentThreadResponse>(`${base}/documents/${documentId}/thread`),

    createEdge: (payload: CreateDocumentEdgePayload) =>
      api.post<DocumentEdge>(`${base}/edges`, payload),

    confirmEdge,

    rejectEdge: (edgeId: number, payload?: RejectDocumentEdgePayload) =>
      api.post<DocumentEdge>(`${base}/edges/${edgeId}/reject`, payload ?? {}),

    deleteEdge: (edgeId: number) => api.delete<DocumentEdge>(`${base}/edges/${edgeId}`),

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
