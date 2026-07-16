/**
 * Document Control API client — controlled document lifecycle.
 */
import type { AxiosInstance } from 'axios'

export interface ControlledDocumentSummary {
  id: number
  document_number: string
  title: string
  document_type: string
  category: string
  current_version: string
  status: string
  department: string | null
  owner_name: string | null
  effective_date: string | null
  next_review_date: string | null
  is_overdue: boolean
}

export interface ControlledDocumentListResponse {
  total: number
  documents: ControlledDocumentSummary[]
}

export interface ControlledDocumentVersion {
  id: number
  version_number: string
  change_summary: string
  change_type: string
  status: string
  is_immutable?: boolean
  read_only?: boolean
  created_by_name: string | null
  created_at: string | null
  approved_by_name: string | null
  approved_date: string | null
  effective_date?: string | null
}

export interface ControlledDocumentDistribution {
  id: number
  recipient_name: string
  recipient_type: string
  distribution_type: string
  copy_number: string | null
  acknowledged: boolean
  acknowledged_date: string | null
}

export interface ControlledDocumentDetail {
  id: number
  document_number: string
  title: string
  description: string | null
  document_type: string
  category: string
  subcategory: string | null
  current_version: string
  status: string
  published_version?: string | null
  working_version?: string | null
  department: string | null
  author_name: string | null
  owner_name: string | null
  approver_name: string | null
  approved_date: string | null
  effective_date: string | null
  expiry_date: string | null
  review_frequency_months: number
  next_review_date: string | null
  last_review_date: string | null
  file_name: string | null
  file_path: string | null
  file_size: number | null
  file_type: string | null
  relevant_standards: string[] | null
  relevant_clauses: string[] | null
  access_level: string
  is_confidential: boolean
  training_required: boolean
  view_count: number
  download_count: number
  versions: ControlledDocumentVersion[]
  distributions: ControlledDocumentDistribution[]
}

export interface ControlledDocumentCreate {
  title: string
  description?: string
  document_type: string
  category: string
  subcategory?: string
  department?: string
  author_name?: string
  owner_name?: string
  review_frequency_months?: number
}

export interface ControlledDocumentGoldenThread {
  controlled_document: Pick<
    ControlledDocumentDetail,
    'id' | 'document_number' | 'title' | 'current_version' | 'status'
  >
  library_document_candidate: {
    id: number
    reference_number: string | null
    title: string
    version: string
    status: string
    matching_fields: string[]
  } | null
  evidence_links: Array<{
    id: number
    clause_id: string
    status: string
    signal_type: string
    scheme: string | null
    confidence: number | null
    linked_by: string
    title: string | null
    rationale: string | null
    created_at: string | null
  }>
  integrity: {
    relationship_state: 'unverified_candidate' | 'ambiguous' | 'not_found'
    hard_fk_present: boolean
    message: string
  }
  publish_plan: {
    should_run: boolean
    denied: boolean
    deny_reason: string | null
    documents_hard_fk_gap: boolean
    steps: string[]
  }
}

export function createDocumentControlApi(api: AxiosInstance) {
  const base = '/api/v1/document-control'

  return {
    list: (params?: { search?: string; status?: string; skip?: number; limit?: number }) =>
      api.get<ControlledDocumentListResponse>(`${base}/`, { params }),

    get: (documentId: number) =>
      api.get<ControlledDocumentDetail>(`${base}/${documentId}`),

    goldenThread: (documentId: number) =>
      api.get<ControlledDocumentGoldenThread>(`${base}/${documentId}/golden-thread`),

    create: (data: ControlledDocumentCreate) =>
      api.post<{
        id: number
        document_number: string
        title?: string
        status: string
        current_version: string
        version?: ControlledDocumentVersion
      }>(`${base}/`, data),

    submitForApproval: (documentId: number) =>
      api.post(`${base}/${documentId}/submit-for-approval`),

    createVersion: (
      documentId: number,
      data: {
        change_summary: string
        change_reason?: string
        change_type?: string
        is_major_version?: boolean
      },
    ) =>
      api.post<{
        id: number
        version_number: string
        status: string
        is_immutable: boolean
        read_only: boolean
        message: string
      }>(`${base}/${documentId}/versions`, data),

    publish: (documentId: number, versionId?: number) =>
      api.post<{
        id: number
        current_version: string
        status: string
        version: ControlledDocumentVersion
        message: string
      }>(`${base}/${documentId}/publish`, null, {
        params: versionId ? { version_id: versionId } : undefined,
      }),

    distribute: (
      documentId: number,
      data: {
        recipient_type: string
        recipient_name: string
        recipient_id?: number
        recipient_email?: string
        acknowledgment_required?: boolean
      },
    ) => api.post(`${base}/${documentId}/distribute`, data),
  }
}
