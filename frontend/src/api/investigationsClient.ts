/**
 * Investigations API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

/** Minimal paginated shape used by investigation list responses. */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip?: number
  limit?: number
  page?: number
  page_size?: number
  pages?: number
  total_pages?: number
}

// ============ Investigation Types ============
export interface Investigation {
  id: number
  reference_number: string
  template_id: number
  assigned_entity_type: 'road_traffic_collision' | 'reporting_incident' | 'complaint' | 'near_miss'
  assigned_entity_id: number
  assigned_entity_reference?: string | null
  status: 'draft' | 'in_progress' | 'under_review' | 'completed' | 'closed'
  /** HSG245-aligned investigation depth from source severity. */
  level?: 'minimal' | 'low' | 'medium' | 'high' | null
  title: string
  description?: string
  data: Record<string, unknown>
  started_at?: string
  completed_at?: string
  assigned_to_user_id?: number | null
  created_at: string
  updated_at?: string
}

export interface InvestigationCreate {
  template_id: number
  assigned_entity_type: string
  assigned_entity_id: number
  title: string
  description?: string
}

// === From-Record Types (Stage 2.1) ===
export interface CreateFromRecordRequest {
  source_type: 'near_miss' | 'road_traffic_collision' | 'complaint' | 'reporting_incident'
  source_id: number
  title: string
  template_id?: number
}

export interface CreateFromRecordError {
  error_code:
    | 'VALIDATION_ERROR'
    | 'SOURCE_NOT_FOUND'
    | 'INV_ALREADY_EXISTS'
    | 'TEMPLATE_NOT_FOUND'
    | 'INTERNAL_ERROR'
  message: string
  details?: {
    existing_investigation_id?: number
    existing_reference_number?: string
    source_type?: string
    source_id?: number
  }
  request_id?: string
}

export interface SourceRecordItem {
  source_id: number
  display_label: string
  reference_number: string
  status: string
  created_at: string
  investigation_id: number | null
  investigation_reference: string | null
}

export interface SourceRecordsResponse {
  items: SourceRecordItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
  source_type: string
}

/**
 * Investigation update payload - all fields optional for partial updates.
 */
export interface InvestigationUpdate {
  title?: string
  status?: string
  data?: Record<string, unknown>
  notes?: string
  assigned_to_user_id?: number | null
  closure_override?: boolean
  closure_override_reason?: string
}

/**
 * Autosave payload with version for optimistic locking.
 */
export interface InvestigationAutosave {
  data: Record<string, unknown>
  version: number
}

// ============ Investigation Stage 1 API Types ============

export interface TimelineEvent {
  id: number
  created_at: string
  event_type: string
  field_path?: string
  old_value?: string
  new_value?: string
  actor_id?: number
  actor_name?: string
  event_metadata?: Record<string, unknown>
}

export interface TimelineResponse {
  items: TimelineEvent[]
  total: number
  page: number
  page_size: number
  investigation_id: number
}

export interface InvestigationComment {
  id: number
  investigation_id: number
  created_at: string
  author_id: number
  content: string
  section_id?: string
  field_id?: string
  parent_comment_id?: number
  deleted_at?: string | null
}

export interface CommentsResponse {
  items: InvestigationComment[]
  total: number
  page: number
  page_size: number
}

export interface CustomerPackSummary {
  id: number
  investigation_id?: number
  generated_at: string
  pack_uuid: string
  audience: string
  checksum_sha256?: string
  generated_by_id?: number
  /** INV-C17 — server-owned review/issue facts. Absent on packs generated before C17. */
  redaction_review_cleared_at?: string | null
  redaction_review_at?: string | null
  redaction_review_by_id?: number | null
  issued_at?: string | null
  issued_by_id?: number | null
  issued_pdf_sha256?: string | null
  disclosure_count?: number
}

export interface PacksResponse {
  items: CustomerPackSummary[]
  total: number
  page: number
  page_size: number
  investigation_id: number
}

export interface GeneratedCustomerPack {
  pack_id: number
  pack_uuid: string
  audience: string
  investigation_id: number
  investigation_reference: string
  generated_at: string
  content: string
  redaction_log: Record<string, unknown>[]
  included_assets: Record<string, unknown>[]
  checksum_sha256?: string
}

export interface ClosureBlockingItem {
  kind: string
  id: number
  reference_number: string
  title: string
  status: string
  action_key: string
  unblock_hint: string
}

export interface ClosureMissingItem {
  code: string
  section_key: string
  section_label: string
  field_key?: string | null
  field_label?: string | null
  path: string
}

export interface ClosureValidation {
  can_close: boolean
  can_complete?: boolean
  reasons: string[]
  completion_reasons?: string[]
  open_work?: ClosureBlockingItem[]
  open_work_count?: number
  /** Named section/field blockers behind the MISSING_REQUIRED_* reason codes. */
  missing_items?: ClosureMissingItem[]
}

// ============ Investigation Template Types ============

export interface InvestigationTemplate {
  id: number
  name: string
  description?: string
  version: string
  is_active: boolean
  structure: Record<string, unknown>
  applicable_entity_types: string[]
  created_at: string
  updated_at: string
  created_by_id?: number
  updated_by_id?: number
}

export interface InvestigationTemplateCreate {
  name: string
  description?: string
  version?: string
  is_active?: boolean
  structure: Record<string, unknown>
  applicable_entity_types: string[]
}

export interface InvestigationTemplateUpdate {
  name?: string
  description?: string
  version?: string
  is_active?: boolean
  structure?: Record<string, unknown>
  applicable_entity_types?: string[]
}

export interface InvestigationTemplateListResponse {
  items: InvestigationTemplate[]
  total: number
  page: number
  page_size: number
  pages: number
}

/**
 * One investigation finding, as a row (INV-C7).
 *
 * Before C7 `findings` was a single string on `investigation.data`. It is still
 * written there — the closure gate and the generated pack read it — but the rows
 * are now what the editor edits, and the string is derived from them server-side.
 */
export interface InvestigationFinding {
  id: number
  investigation_id: number
  body: string
  sort_order: number
  created_by_id?: number | null
  created_at?: string | null
  updated_at?: string | null
}

/**
 * The run's findings, in order.
 *
 * `items: []` is a normal, successful answer. `findings_text` is the exact string
 * the server stored back onto `investigation.data`, returned so callers never have
 * to re-derive it (and risk deriving it differently).
 */
export interface InvestigationFindingsResponse {
  items: InvestigationFinding[]
  total: number
  investigation_id: number
  findings_text: string
}

/** Optional filters for investigation list (status / entity_type / smart search q). */
export interface InvestigationListParams {
  status?: string
  entity_type?: string
  /** Smart search — title/ref/people/actions/comments when BE honors q (PR-5). */
  q?: string
}

export function createInvestigationsApi(api: AxiosInstance) {
  return {
    /**
     * List investigations.
     * Third arg accepts legacy `status` string or `{ status, entity_type, q }`.
     * `q` is forwarded for smart search; ignored by API until PR-5 BE lands.
     */
    list: (page = 1, pageSize = 10, statusOrOptions?: string | InvestigationListParams) => {
      const options: InvestigationListParams =
        typeof statusOrOptions === 'string' ? { status: statusOrOptions } : (statusOrOptions ?? {})
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      })
      if (options.status) params.set('status', options.status)
      if (options.entity_type) params.set('entity_type', options.entity_type)
      if (options.q?.trim()) params.set('q', options.q.trim())
      return api.get<PaginatedResponse<Investigation>>(`/api/v1/investigations/?${params}`)
    },
    create: (data: InvestigationCreate) => api.post<Investigation>('/api/v1/investigations/', data),
    get: (id: number) => api.get<Investigation>(`/api/v1/investigations/${id}`),
    /**
     * Update investigation with partial data.
     * Returns updated investigation on success.
     */
    update: (id: number, data: InvestigationUpdate) =>
      api.patch<Investigation>(`/api/v1/investigations/${id}`, data),
    /**
     * Autosave investigation with version-based optimistic locking.
     * Returns 409 CONFLICT if version mismatch (stale data).
     */
    autosave: (id: number, data: InvestigationAutosave) =>
      api.patch<Investigation>(`/api/v1/investigations/${id}/autosave`, data),
    /**
     * Create investigation from source record using proper JSON body.
     * Returns 201 on success, 404 if source not found, 409 if already investigated.
     */
    createFromRecord: (data: CreateFromRecordRequest) =>
      api.post<Investigation>('/api/v1/investigations/from-record', data),
    /**
     * List source records available for investigation creation.
     * Records with investigation_id !== null are already investigated.
     */
    listSourceRecords: (
      source_type: string,
      options?: { q?: string; page?: number; size?: number },
    ) => {
      const params = new URLSearchParams({ source_type })
      if (options?.q) params.set('q', options.q)
      if (options?.page) params.set('page', String(options.page))
      if (options?.size) params.set('page_size', String(options.size))
      return api.get<SourceRecordsResponse>(`/api/v1/investigations/source-records?${params}`)
    },

    // ============ Stage 1 Endpoints ============

    /**
     * Get timeline events for an investigation.
     * Ordered by created_at DESC, id DESC.
     */
    getTimeline: (id: number, options?: { page?: number; page_size?: number; type?: string }) => {
      const params = new URLSearchParams()
      if (options?.page) params.set('page', String(options.page))
      if (options?.page_size) params.set('page_size', String(options.page_size))
      if (options?.type) params.set('event_type', options.type)
      return api.get<TimelineResponse>(`/api/v1/investigations/${id}/timeline?${params}`)
    },

    /**
     * Get comments for an investigation.
     * Ordered by created_at DESC, id DESC.
     */
    getComments: (id: number, options?: { page?: number; page_size?: number }) => {
      const params = new URLSearchParams()
      if (options?.page) params.set('page', String(options.page))
      if (options?.page_size) params.set('page_size', String(options.page_size))
      return api.get<CommentsResponse>(`/api/v1/investigations/${id}/comments?${params}`)
    },

    /**
     * Add a comment to an investigation.
     */
    addComment: (id: number, body: string) =>
      api.post<InvestigationComment>(`/api/v1/investigations/${id}/comments`, {
        content: body,
      }),

    // ============ Findings rows (INV-C7) ============

    /**
     * List an investigation's findings, in order.
     *
     * The first call for a run that still holds only the legacy `data.findings`
     * string converts that string into rows server-side, once. Every call after
     * that returns the stored rows, so calling this repeatedly is safe.
     */
    listFindings: (id: number) =>
      api.get<InvestigationFindingsResponse>(`/api/v1/investigations/${id}/findings`),

    /**
     * Append a finding.
     *
     * All four mutations resolve to the whole ordered list, because `sort_order` is
     * assigned server-side — a caller holding only the row it just changed would
     * have to guess the new order.
     */
    createFinding: (id: number, body: string) =>
      api.post<InvestigationFindingsResponse>(`/api/v1/investigations/${id}/findings`, { body }),

    /** Rewrite one finding's text. Position is unaffected. */
    updateFinding: (id: number, findingId: number, body: string) =>
      api.patch<InvestigationFindingsResponse>(
        `/api/v1/investigations/${id}/findings/${findingId}`,
        { body },
      ),

    /** Remove one finding. Removing the last one leaves a valid empty list. */
    deleteFinding: (id: number, findingId: number) =>
      api.delete<InvestigationFindingsResponse>(
        `/api/v1/investigations/${id}/findings/${findingId}`,
      ),

    /**
     * Apply a new order.
     *
     * `findingIds` must be every one of this run's findings, each once — the server
     * refuses a partial list with 400 rather than applying it, so a stale editor
     * cannot drop a finding another tab added.
     */
    reorderFindings: (id: number, findingIds: number[]) =>
      api.post<InvestigationFindingsResponse>(`/api/v1/investigations/${id}/findings/reorder`, {
        finding_ids: findingIds,
      }),

    /**
     * Get customer pack summaries for an investigation.
     * Does NOT include full content for security.
     */
    getPacks: (id: number, options?: { page?: number; page_size?: number }) => {
      const params = new URLSearchParams()
      if (options?.page) params.set('page', String(options.page))
      if (options?.page_size) params.set('page_size', String(options.page_size))
      return api.get<PacksResponse>(`/api/v1/investigations/${id}/packs?${params}`)
    },

    /**
     * Generate a new customer pack for an investigation.
     */
    generatePack: (id: number, audience: string) =>
      api.post<GeneratedCustomerPack>(
        `/api/v1/investigations/${id}/customer-pack?audience=${encodeURIComponent(audience)}`,
      ),

    /**
     * Get closure validation status for an investigation.
     * Inline honesty UI on InvestigationDetail — do not global-toast on probe failure.
     */
    getClosureValidation: (id: number) =>
      api.get<ClosureValidation>(`/api/v1/investigations/${id}/closure-validation`, {
        suppressErrorToast: true,
      }),

    /**
     * Create a formal CAPA linked to this investigation (parent auto-set server-side).
     */
    createCapa: (
      id: number,
      body?: {
        title?: string
        description?: string
        assignee_id?: number
        assignee_email?: string
        assignee_name?: string
        due_date?: string
        priority?: string
        why_level?: number
        five_whys_id?: number
      },
    ) =>
      api.post<{
        id: number
        reference_number: string
        title: string
        source_type?: string
        source_id?: number
      }>(`/api/v1/investigations/${id}/capa`, body ?? {}),

    // ============ Investigation Template Endpoints ============

    listTemplates: (options?: { page?: number; page_size?: number; is_active?: boolean }) => {
      const params = new URLSearchParams()
      if (options?.page) params.set('page', String(options.page))
      if (options?.page_size) params.set('page_size', String(options.page_size))
      if (options?.is_active != null) params.set('is_active', String(options.is_active))
      const query = params.toString()
      return api.get<InvestigationTemplateListResponse>(
        query ? `/api/v1/investigation-templates/?${query}` : '/api/v1/investigation-templates/',
      )
    },

    getTemplate: (id: number) =>
      api.get<InvestigationTemplate>(`/api/v1/investigation-templates/${id}`),

    createTemplate: (data: InvestigationTemplateCreate) =>
      api.post<InvestigationTemplate>('/api/v1/investigation-templates/', data),

    updateTemplate: (id: number, data: InvestigationTemplateUpdate) =>
      api.patch<InvestigationTemplate>(`/api/v1/investigation-templates/${id}`, data),

    deleteTemplate: (id: number) => api.delete<void>(`/api/v1/investigation-templates/${id}`),
  }
}
