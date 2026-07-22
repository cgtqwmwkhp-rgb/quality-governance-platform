/**
 * Audits API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

/** Minimal paginated shape used by audits list responses. */
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

// ============ Audit Types ============
export type ExternalAuditType = 'customer' | 'iso' | 'planet_mark' | 'achilles_uvdb' | 'other'

export interface AuditRun {
  id: number
  reference_number: string
  template_id: number
  template_version: number
  title?: string
  location?: string
  location_details?: string
  notes?: string
  source_origin?: string
  assurance_scheme?: string
  external_body_name?: string
  external_auditor_name?: string
  external_reference?: string
  source_document_asset_id?: number
  source_document_label?: string
  is_external_audit_import?: boolean
  is_external_import_intake?: boolean
  status: 'draft' | 'scheduled' | 'in_progress' | 'pending_review' | 'completed' | 'cancelled'
  scheduled_date?: string
  due_date?: string
  started_at?: string
  completed_at?: string
  score?: number | null
  max_score?: number | null
  score_percentage?: number | null
  passed?: boolean | null
  created_at: string
  /** Branching/reporting dimensions (PR: audit-branching-reporting). */
  assessment_mode?: string | null
  asset_id?: number | null
  asset_type_id?: number | null
  engineer_id?: number | null
  location_id?: number | null
  customer_code?: string | null
}

export interface AuditFinding {
  id: number
  reference_number: string
  run_id: number
  question_id?: number
  title: string
  description: string
  severity: string
  finding_type: string
  status: 'open' | 'in_progress' | 'pending_verification' | 'closed' | 'deferred'
  corrective_action_required: boolean
  corrective_action_due_date?: string
  /** Linked enterprise risk ids (risks_v2) when escalated from this finding. */
  risk_ids?: number[] | null
  created_at: string
  /**
   * Optional loop enrichment from CAPA closure bridge / findings list when present.
   * FE consumes these when available and falls back to Actions list otherwise.
   */
  linked_capa_display_status?: string | null
  linked_capa_assignee_email?: string | null
  linked_capa_action_id?: number | null
  linked_capa_action_key?: string | null
  linked_capa_reference?: string | null
  /** Optional closure note accepted by tolerant writers; ignored if API omits the field. */
  closure_note?: string | null
}

/** CAPA created (or returned) from POST /audits/findings/{id}/capa. */
export interface FindingCapaResponse {
  id: number
  reference_number: string
  title: string
  description?: string | null
  capa_type: string
  status: string
  priority: string
  source_type?: string | null
  source_id?: number | null
  assigned_to_id?: number | null
  created_by_id: number
  tenant_id?: number | null
  due_date?: string | null
  created_at: string
  updated_at?: string | null
}

export interface AuditTemplate {
  id: number
  reference_number: string
  name: string
  description?: string
  category?: string
  audit_type: string
  tags?: string[]
  version: number
  is_active: boolean
  is_published: boolean
  created_at: string
  updated_at?: string
  archived_at?: string | null
  scoring_method?: string
  question_count?: number
  section_count?: number
}

export interface CategoryCount {
  category: string
  count: number
}

export interface BatchImportResult {
  imported: number
  skipped: number
  errors: string[]
  templates: AuditTemplate[]
}

export interface AuditTemplateCreate {
  name: string
  description?: string
  category?: string
  audit_type?: string
  scoring_method?: string
  passing_score?: number
}

export interface AuditTemplateUpdate {
  name?: string
  description?: string
  category?: string
  audit_type?: string
  scoring_method?: string
  passing_score?: number
  expected_updated_at?: string
}

export interface AuditRunDetail extends AuditRun {
  template_name?: string
  responses: AuditResponse[]
  findings: AuditFinding[]
  completion_percentage: number
}

export interface AuditRunCreate {
  template_id?: number
  title?: string
  location?: string
  location_details?: string
  scheduled_date?: string
  due_date?: string
  notes?: string
  external_audit_type?: ExternalAuditType
  source_origin?: string
  assurance_scheme?: string
  external_body_name?: string
  external_auditor_name?: string
  external_reference?: string
  source_document_asset_id?: number
  source_document_label?: string
  /** Branching/reporting dimensions (PR: audit-branching-reporting). */
  assessment_mode?: string
  asset_id?: number
  asset_type_id?: number
  engineer_id?: number
  location_id?: number
  customer_code?: string
}

export interface AuditRunUpdate {
  title?: string
  location?: string
  location_details?: string
  status?: 'draft' | 'scheduled' | 'in_progress' | 'pending_review' | 'completed' | 'cancelled'
  scheduled_date?: string
  due_date?: string
  assigned_to_id?: number
  notes?: string
  source_origin?: string
  assurance_scheme?: string
  external_body_name?: string
  external_auditor_name?: string
  external_reference?: string
  source_document_asset_id?: number
  source_document_label?: string
  /** Branching/reporting dimensions (PR: audit-branching-reporting). */
  assessment_mode?: string | null
  asset_id?: number | null
  asset_type_id?: number | null
  engineer_id?: number | null
  location_id?: number | null
  customer_code?: string | null
}

export interface AuditTemplateDetail {
  id: number
  reference_number?: string
  name: string
  description?: string
  category?: string
  audit_type: string
  frequency?: string
  version: number
  scoring_method: string
  passing_score?: number
  allow_offline: boolean
  require_gps: boolean
  require_signature: boolean
  require_approval: boolean
  auto_create_findings: boolean
  is_published: boolean
  is_active: boolean
  created_by_id?: number
  sections: AuditSection[]
  section_count: number
  question_count: number
  created_at: string
  updated_at: string
}

/** Section-level composition rule. Null/missing dimension = unrestricted. */
export interface SectionApplicabilityRules {
  assessment_modes?: string[] | null
  asset_type_ids?: number[] | null
}

export interface AuditSectionCreate {
  title: string
  description?: string
  sort_order?: number
  weight?: number
  applicability_rules?: SectionApplicabilityRules | null
}

export interface AuditSectionUpdate {
  title?: string
  description?: string
  sort_order?: number
  weight?: number
  applicability_rules?: SectionApplicabilityRules | null
}

export interface QuestionOptionBase {
  value: string
  label: string
  score?: number
  is_correct?: boolean
  triggers_finding?: boolean
  finding_severity?: string
}

export interface EvidenceRequirement {
  required: boolean
  min_attachments?: number
  max_attachments?: number
  allowed_types?: string[]
  require_photo?: boolean
  require_signature?: boolean
}

/** Mirrors backend `ConditionalLogicRule` (src/api/schemas/audit.py). */
export interface ConditionalLogicRule {
  source_question_id: string | number
  operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than' | 'is_empty' | 'is_not_empty'
  value?: string | number | boolean | null
  action: 'show' | 'hide'
}

export type QuestionCriticality = 'essential' | 'required' | 'good_to_have'

export interface AuditQuestionCreate {
  section_id?: number
  question_text: string
  question_type: string
  description?: string
  help_text?: string
  is_required?: boolean
  allow_na?: boolean
  max_score?: number
  max_value?: number | null
  weight?: number
  options?: QuestionOptionBase[]
  evidence_requirements?: EvidenceRequirement
  sort_order?: number
  risk_category?: string
  risk_weight?: number
  failure_triggers_action?: boolean
  positive_answer?: 'yes' | 'no'
  criticality?: QuestionCriticality
  conditional_logic?: ConditionalLogicRule[] | null
}

export interface AuditQuestionUpdate {
  question_text?: string
  question_type?: string
  description?: string
  help_text?: string
  is_required?: boolean
  allow_na?: boolean
  max_score?: number
  weight?: number
  options?: QuestionOptionBase[]
  min_value?: number | null
  max_value?: number | null
  evidence_requirements?: EvidenceRequirement | null
  decimal_places?: number | null
  min_length?: number | null
  max_length?: number | null
  sort_order?: number
  risk_category?: string
  risk_weight?: number
  failure_triggers_action?: boolean
  positive_answer?: 'yes' | 'no'
  is_active?: boolean
  criticality?: QuestionCriticality
  conditional_logic?: ConditionalLogicRule[] | null
}

export interface AuditSection {
  id: number
  template_id: number
  title: string
  description?: string
  sort_order: number
  weight: number
  is_repeatable: boolean
  max_repeats?: number
  is_active: boolean
  questions: AuditQuestion[]
  applicability_rules?: SectionApplicabilityRules | null
  created_at: string
  updated_at: string
}

export interface AuditQuestion {
  id: number
  template_id: number
  section_id?: number
  question_text: string
  question_type: string
  description?: string
  help_text?: string
  is_required: boolean
  allow_na: boolean
  is_active: boolean
  max_score?: number
  weight: number
  options?: QuestionOptionBase[]
  min_value?: number
  max_value?: number
  decimal_places?: number
  min_length?: number
  max_length?: number
  sort_order: number
  risk_category?: string
  risk_weight?: number
  evidence_requirements?: EvidenceRequirement | null
  failure_triggers_action: boolean
  positive_answer?: 'yes' | 'no'
  criticality?: string
  conditional_logic?: ConditionalLogicRule[] | null
  created_at: string
  updated_at: string
}

export type ResponseApplicability = 'applicable' | 'not_applicable_by_composition' | 'hidden_by_logic'

export interface AuditResponse {
  id: number
  run_id: number
  question_id: number
  response_value?: string
  response_json?: Record<string, unknown> | null
  is_na?: boolean
  score?: number
  max_score?: number
  notes?: string
  applicability?: ResponseApplicability | null
  created_at: string
}

export interface AuditResponseCreate {
  question_id: number
  response_value?: string | null
  response_json?: Record<string, unknown> | null
  is_na?: boolean
  score?: number | null
  max_score?: number | null
  notes?: string | null
  applicability?: ResponseApplicability | null
}

export interface AuditResponseUpdate {
  response_value?: string | null
  response_json?: Record<string, unknown> | null
  is_na?: boolean
  score?: number | null
  max_score?: number | null
  notes?: string | null
  applicability?: ResponseApplicability | null
}

export interface AuditFindingCreate {
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'observation'
  finding_type?: 'nonconformity' | 'observation' | 'opportunity' | 'positive'
  question_id?: number
  clause_ids?: number[]
  control_ids?: number[]
  risk_ids?: number[]
  corrective_action_required?: boolean
  corrective_action_due_date?: string
}

export interface AuditFindingUpdate {
  title?: string
  description?: string
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'observation'
  finding_type?: 'nonconformity' | 'observation' | 'opportunity' | 'positive'
  status?: 'open' | 'in_progress' | 'pending_verification' | 'closed' | 'deferred'
  corrective_action_required?: boolean
  corrective_action_due_date?: string
  /** Tolerant optional fields — sibling CAPA bridge may persist; current API may ignore. */
  closure_note?: string
  closure_override?: boolean
  closure_override_reason?: string
}

// ============ Audit Analytics (reporting pack) ============

export interface AuditAnalyticsSummary {
  period_days: number
  totals: number
  completed: number
  in_progress: number
  avg_score: number
  pass_rate: number
  essential_compliance_pct: number
  incomplete_critical_count: number
}

export type AuditAnalyticsGroupBy =
  | 'asset_type'
  | 'assessment_mode'
  | 'template'
  | 'criticality'
  | 'customer'
  | 'location'
  | 'engineer'
  | 'week'

export interface AuditAnalyticsDimensionItem {
  key: string
  label: string
  run_count: number
  completed_count: number
  avg_score: number
  fail_rate: number
  essential_compliance_pct?: number | null
}

export interface AuditAnalyticsDimensionsResponse {
  group_by: string
  period_days: number
  items: AuditAnalyticsDimensionItem[]
}

export interface CriticalQueueItem {
  run_id: number
  run_reference_number?: string | null
  template_id: number
  template_name?: string | null
  question_id: number
  question_text: string
  reason: 'unanswered' | 'failed_open_finding'
  finding_id?: number | null
  finding_status?: string | null
}

export interface CriticalQueueResponse {
  total: number
  items: CriticalQueueItem[]
}

export function createAuditsApi(api: AxiosInstance) {
  return {
  // Analytics / reporting pack
  getAnalyticsSummary: (days = 90) =>
    api.get<AuditAnalyticsSummary>('/api/v1/audits/analytics/summary', { params: { days } }),
  getAnalyticsDimensions: (groupBy: AuditAnalyticsGroupBy, days = 90) =>
    api.get<AuditAnalyticsDimensionsResponse>('/api/v1/audits/analytics/dimensions', {
      params: { group_by: groupBy, days },
    }),
  getCriticalQueue: (limit = 200) =>
    api.get<CriticalQueueResponse>('/api/v1/audits/analytics/critical-queue', {
      params: { limit },
    }),
  exportAnalyticsCsv: (days = 90) =>
    api.get<Blob>('/api/v1/audits/analytics/export.csv', {
      params: { days },
      responseType: 'blob',
    }),

  // Template ↔ asset type composition links
  linkTemplateAssetType: (templateId: number, assetTypeId: number) =>
    api.post(`/api/v1/audits/templates/${templateId}/asset-types/${assetTypeId}`),
  unlinkTemplateAssetType: (templateId: number, assetTypeId: number) =>
    api.delete(`/api/v1/audits/templates/${templateId}/asset-types/${assetTypeId}`),

  // Category summary
  listCategories: () => api.get<CategoryCount[]>('/api/v1/audit-templates/categories'),
  // Batch import
  batchImportTemplates: (directoryPath: string) =>
    api.post<BatchImportResult>('/api/v1/xml-import/batch-import', {
      directory_path: directoryPath,
    }),
  // Templates
  listTemplates: (
    page = 1,
    pageSize = 10,
    filters?: { is_published?: boolean; search?: string; category?: string; audit_type?: string },
  ) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })
    if (filters?.is_published !== undefined) {
      params.set('is_published', String(filters.is_published))
    }
    if (filters?.search) {
      params.set('search', filters.search)
    }
    if (filters?.category) {
      params.set('category', filters.category)
    }
    if (filters?.audit_type) {
      params.set('audit_type', filters.audit_type)
    }
    return api.get<PaginatedResponse<AuditTemplate>>(
      `/api/v1/audits/templates?${params.toString()}`,
    )
  },
  getTemplate: (id: number) => api.get<AuditTemplateDetail>(`/api/v1/audits/templates/${id}`),
  createTemplate: (data: AuditTemplateCreate) =>
    api.post<AuditTemplate>('/api/v1/audits/templates', data),
  updateTemplate: (id: number, data: AuditTemplateUpdate) =>
    api.patch<AuditTemplate>(`/api/v1/audits/templates/${id}`, data),
  publishTemplate: (id: number) =>
    api.post<AuditTemplate>(`/api/v1/audits/templates/${id}/publish`),
  cloneTemplate: (id: number) => api.post<AuditTemplate>(`/api/v1/audits/templates/${id}/clone`),
  deleteTemplate: (id: number) => api.delete(`/api/v1/audits/templates/${id}`),
  listArchivedTemplates: (page = 1, size = 20) =>
    api.get<PaginatedResponse<AuditTemplate>>(
      `/api/v1/audits/templates/archived?page=${page}&page_size=${size}`,
    ),
  restoreTemplate: (id: number) =>
    api.post<AuditTemplate>(`/api/v1/audits/templates/${id}/restore`),

  // Sections
  createSection: (templateId: number, data: AuditSectionCreate) =>
    api.post<AuditSection>(`/api/v1/audits/templates/${templateId}/sections`, data),
  updateSection: (sectionId: number, data: AuditSectionUpdate) =>
    api.patch<AuditSection>(`/api/v1/audits/sections/${sectionId}`, data),
  deleteSection: (sectionId: number) => api.delete(`/api/v1/audits/sections/${sectionId}`),

  // Questions
  createQuestion: (templateId: number, data: AuditQuestionCreate) =>
    api.post<AuditQuestion>(`/api/v1/audits/templates/${templateId}/questions`, data),
  updateQuestion: (questionId: number, data: AuditQuestionUpdate) =>
    api.patch<AuditQuestion>(`/api/v1/audits/questions/${questionId}`, data),
  deleteQuestion: (questionId: number) => api.delete(`/api/v1/audits/questions/${questionId}`),

  // Runs
  listRuns: (page = 1, pageSize = 10) =>
    api.get<PaginatedResponse<AuditRun>>(`/api/v1/audits/runs?page=${page}&page_size=${pageSize}`),
  createRun: (data: AuditRunCreate) => api.post<AuditRun>('/api/v1/audits/runs', data),
  getRun: (id: number) => api.get<AuditRun>(`/api/v1/audits/runs/${id}`),
  getRunDetail: (id: number) => api.get<AuditRunDetail>(`/api/v1/audits/runs/${id}`),
  updateRun: (id: number, data: AuditRunUpdate) =>
    api.patch<AuditRun>(`/api/v1/audits/runs/${id}`, data),
  startRun: (id: number) => api.post<AuditRun>(`/api/v1/audits/runs/${id}/start`),
  completeRun: (id: number) => api.post<AuditRun>(`/api/v1/audits/runs/${id}/complete`),

  // Responses
  createResponse: (runId: number, data: AuditResponseCreate) =>
    api.post<AuditResponse>(`/api/v1/audits/runs/${runId}/responses`, data),
  updateResponse: (responseId: number, data: AuditResponseUpdate) =>
    api.patch<AuditResponse>(`/api/v1/audits/responses/${responseId}`, data),

  // Findings
  listFindings: (page = 1, pageSize = 10, runId?: number) =>
    api.get<PaginatedResponse<AuditFinding>>(
      `/api/v1/audits/findings?page=${page}&page_size=${pageSize}${runId ? `&run_id=${runId}` : ''}`,
    ),
  createFinding: (runId: number, data: AuditFindingCreate) =>
    api.post<AuditFinding>(`/api/v1/audits/runs/${runId}/findings`, data),
  updateFinding: (findingId: number, data: AuditFindingUpdate) =>
    api.patch<AuditFinding>(`/api/v1/audits/findings/${findingId}`, data),
  flagFindingToRisk: (findingId: number, data: { severity?: 'critical' | 'high' | 'medium' | 'low' } = {}) =>
    api.post<AuditFinding>(`/api/v1/audits/findings/${findingId}/flag-risk`, data),
  createFindingCapa: (
    findingId: number,
    body: { title?: string; description?: string; assignee_email?: string } = {},
  ) =>
    api.post<FindingCapaResponse>(`/api/v1/audits/findings/${findingId}/capa`, body),
}
}
