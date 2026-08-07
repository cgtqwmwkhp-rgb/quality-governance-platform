/**
 * Compliance Schedule API client (Wave 1).
 */
import type { AxiosInstance } from 'axios'

export type ComplianceStatus = 'current' | 'due_soon' | 'overdue'

export interface ComplianceRequirement {
  id: number
  external_id: string
  tenant_id: number
  reference_number: string
  template_id?: number | null
  location_id?: number | null
  title: string
  taxonomy_id: string
  description?: string | null
  regulatory_basis?: string | null
  regulatory_standard_id?: number | null
  regulatory_clause_id?: number | null
  frequency_months?: number | null
  frequency_days?: number | null
  anchor: 'completion' | 'schedule'
  statutory: boolean
  next_due_date: string
  last_completed_at?: string | null
  owner_id?: number | null
  is_active: boolean
  status?: ComplianceStatus | null
  created_at: string
  updated_at?: string | null
}

export interface ComplianceRecord {
  id: number
  external_id: string
  tenant_id: number
  reference_number: string
  requirement_id: number
  due_date: string
  outcome: 'completed' | 'missed'
  completed_at?: string | null
  check_passed?: boolean | null
  notes?: string | null
  library_document_id?: number | null
  filing_status: string
  filing_error?: string | null
  created_at: string
  updated_at?: string | null
}

/**
 * Filing payload, mirroring `RecordFileRequest`.
 *
 * Exactly one of `evidence_asset_id` (with `category_id`) or
 * `library_document_id` — the backend rejects a body that sets both or neither,
 * because the two modes authorise differently and a guess would file something.
 */
export type RecordFilePayload =
  | { evidence_asset_id: number; category_id: number; title?: string }
  | { library_document_id: number }

export interface RecordFilingResult {
  record: ComplianceRecord
  library_document_id: number
  pel_doc_ref?: string | null
  linked_existing: boolean
  duplicate_warning: boolean
  duplicate_warning_detail?: Array<{
    document_id: number
    title: string
    reference_number: string
    pel_doc_ref?: string | null
  }> | null
}

export interface CatalogueTemplate {
  id: number
  template_key: string
  title: string
  taxonomy_id: string
  description?: string | null
  regulatory_basis?: string | null
  frequency_months?: number | null
  frequency_days?: number | null
  anchor: 'completion' | 'schedule'
  statutory: boolean
  is_active: boolean
}

export interface ComplianceScheduleStats {
  total_active: number
  current: number
  due_soon: number
  overdue: number
}

export interface LocationCoverageGapItem {
  location_id: number
  location_name: string
  location_kind: string
  has_fra: boolean
  has_fire_drill: boolean
  fra_requirement_id?: number | null
  fire_drill_requirement_id?: number | null
  missing_fra: boolean
  missing_fire_drill: boolean
}

export interface LocationCoverageGaps {
  total_locations: number
  missing_fra: number
  missing_fire_drill: number
  missing_both: number
  items: LocationCoverageGapItem[]
}

export interface ComplianceImportRowError {
  row: number
  code: string
  message: string
  field?: string | null
}

export interface ComplianceImportPreviewRow {
  row: number
  action: string
  template_key: string
  location_id: number
  location_name: string
  title: string
  next_due_date?: string | null
  owner_id?: number | null
}

export interface ComplianceImportValidationReport {
  dry_run: boolean
  total_rows: number
  valid_rows: number
  error_rows: number
  creates: number
  skips: number
  ok: boolean
  errors: ComplianceImportRowError[]
  preview: ComplianceImportPreviewRow[]
}

export interface ComplianceImportCommitResult {
  created_count: number
  created_requirement_ids: number[]
  report: ComplianceImportValidationReport
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface CompleteRecordPayload {
  completed_at?: string
  check_passed?: boolean
  notes?: string
  evidence_asset_ids?: number[]
  due_date?: string
}

/**
 * Create payload, mirroring `RequirementCreate` in
 * `src/api/schemas/compliance_schedule.py`.
 *
 * `template_id` is deliberately absent. The schema accepts it as a
 * client-settable foreign key with no validation, so a wrong value surfaces as
 * an unhandled integrity error rather than a rejected field — not something a
 * form should be able to reach.
 */
export interface RequirementCreatePayload {
  title: string
  taxonomy_id: string
  next_due_date: string
  description?: string | null
  regulatory_basis?: string | null
  regulatory_standard_id?: number | null
  regulatory_clause_id?: number | null
  frequency_months?: number | null
  frequency_days?: number | null
  anchor?: 'completion' | 'schedule'
  statutory?: boolean
  location_id?: number | null
  owner_id?: number | null
}

/**
 * Update payload, mirroring `RequirementUpdate`. Every field is optional and the
 * route applies `exclude_unset`, so an absent key means "leave alone" while an
 * explicit `null` clears the value. Callers must therefore omit keys they do not
 * intend to change rather than sending undefined-ish placeholders.
 */
export type RequirementUpdatePayload = Partial<RequirementCreatePayload> & {
  is_active?: boolean
}

export interface RegulatoryBasisSuggestPayload {
  title: string
  taxonomy_id: string
  description?: string | null
  statutory?: boolean
  requirement_id?: number
}

export interface RegulatoryBasisClarifyPayload extends RegulatoryBasisSuggestPayload {
  answers: Array<{ question_id: string; answer: string }>
}

export interface RegulatoryBasisCandidate {
  label: string
  regulation_or_standard_code: string
  standard_id?: number | null
  clause_ids: number[]
  confidence: number
  rationale: string
  source: string
}

export interface RegulatoryBasisQuestion {
  id: string
  question: string
  options: string[]
  why: string
}

export interface RegulatoryBasisSuggestResult {
  candidates: RegulatoryBasisCandidate[]
  needs_clarification: boolean
  clarifying_questions: RegulatoryBasisQuestion[]
  confidence_threshold: number
  ai_available: boolean
  notice?: string | null
}

export function createComplianceScheduleApi(api: AxiosInstance) {
  // The shared axios instance sets baseURL to the host only, with no version
  // segment, so every client spells `/api/v1` itself. Omitting it here sent all
  // twelve of these requests to paths the server does not serve, and each one
  // answered 404 in every environment.
  const base = '/api/v1/compliance-schedule'

  return {
    listRequirements: (params?: {
      is_active?: boolean
      location_id?: number
      status?: ComplianceStatus
      page?: number
      page_size?: number
    }) => api.get<Paginated<ComplianceRequirement>>(`${base}/requirements`, { params }),

    getRequirement: (id: number) => api.get<ComplianceRequirement>(`${base}/requirements/${id}`),

    createRequirement: (data: RequirementCreatePayload) =>
      api.post<ComplianceRequirement>(`${base}/requirements`, data),

    updateRequirement: (id: number, data: RequirementUpdatePayload) =>
      api.patch<ComplianceRequirement>(`${base}/requirements/${id}`, data),

    deactivateRequirement: (id: number) =>
      api.post<ComplianceRequirement>(`${base}/requirements/${id}/deactivate`),

    suggestRegulatoryBasis: (data: RegulatoryBasisSuggestPayload) =>
      api.post<RegulatoryBasisSuggestResult>(`${base}/regulatory-basis/suggest`, data),

    clarifyRegulatoryBasis: (data: RegulatoryBasisClarifyPayload) =>
      api.post<RegulatoryBasisSuggestResult>(`${base}/regulatory-basis/clarify`, data),

    listRecords: (requirementId: number, params?: { page?: number; page_size?: number }) =>
      api.get<Paginated<ComplianceRecord>>(`${base}/requirements/${requirementId}/records`, {
        params,
      }),

    completeRequirement: (requirementId: number, data: CompleteRecordPayload) =>
      api.post<ComplianceRecord>(`${base}/requirements/${requirementId}/records`, data),

    getRecord: (id: number) => api.get<ComplianceRecord>(`${base}/records/${id}`),

    attachEvidence: (recordId: number, evidence_asset_ids: number[]) =>
      api.post<ComplianceRecord>(`${base}/records/${recordId}/evidence`, { evidence_asset_ids }),

    /**
     * File an occurrence's evidence into the Governance Library (ADR-0020).
     *
     * Deliberately not folded into `completeRequirement`: completing an
     * occurrence records that the work happened and files nothing, and the two
     * being one call is exactly the conflation the ADR forbids.
     */
    fileRecordToLibrary: (recordId: number, data: RecordFilePayload) =>
      api.post<RecordFilingResult>(`${base}/records/${recordId}/file`, data),

    listCatalogue: (active_only = true) =>
      api.get<{ items: CatalogueTemplate[]; total: number }>(`${base}/catalogue`, {
        params: { active_only },
      }),

    activateCatalogue: (
      templateKey: string,
      data?: {
        location_id?: number
        next_due_date?: string
        last_completed_at?: string
        owner_id?: number
      },
    ) => api.post<ComplianceRequirement>(`${base}/catalogue/${templateKey}/activate`, data ?? {}),

    getStats: () => api.get<ComplianceScheduleStats>(`${base}/stats`),

    getLocationCoverageGaps: () =>
      api.get<LocationCoverageGaps>(`${base}/coverage/location-gaps`),

    importDryRun: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return api.post<ComplianceImportValidationReport>(`${base}/import/dry-run`, body, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },

    importCommit: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return api.post<ComplianceImportCommitResult>(`${base}/import/commit`, body, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
  }
}

export type ComplianceScheduleApi = ReturnType<typeof createComplianceScheduleApi>
