/**
 * Workforce API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

// ============ Workforce Development Types ============

export interface AssetType {
  id: number
  category: string
  name: string
  description?: string
  is_active: boolean
}

export interface Asset {
  id: number
  external_id: string
  asset_type_id: number
  asset_number: string
  name: string
  make?: string
  model?: string
  serial_number?: string
  status: string
  site?: string
}

export interface AssessmentRun {
  id: string
  reference_number: string
  template_id: number
  engineer_id: number
  supervisor_id: number
  asset_type_id?: number
  /** Optional asset instance linked to the run (OpenAPI AssessmentRunResponse). */
  asset_id?: number
  title?: string
  location?: string
  status: string
  outcome?: string
  scheduled_date?: string
  started_at?: string
  completed_at?: string
  created_at: string
  /**
   * Soft competency-gate fields from assessment `/start` (OpenAPI AssessmentRunResponse).
   * Present when COMPETENCY_GATE_MODE=soft and competence is not cleared.
   */
  competency_gate_cleared?: boolean
  competency_gate_reason?: string
  competency_gate_mode?: string
  /**
   * Forward-compatible aliases if backend later exposes blocked/message shape
   * (today use competency_gate_cleared / competency_gate_reason).
   */
  competency_gate_blocked?: boolean
  competency_gate_message?: string
}

export interface InductionRun {
  id: string
  reference_number: string
  template_id: number
  engineer_id: number
  supervisor_id: number
  asset_type_id?: number
  title?: string
  stage: string
  status: string
  scheduled_date?: string
  created_at: string
  /**
   * Soft competency-gate fields from induction `/start` (OpenAPI InductionRunResponse).
   * Present when COMPETENCY_GATE_MODE=soft and competence is not cleared.
   */
  competency_gate_cleared?: boolean
  competency_gate_reason?: string
  competency_gate_mode?: string
  /**
   * Forward-compatible aliases if backend later exposes blocked/message shape
   * (today use competency_gate_cleared / competency_gate_reason).
   */
  competency_gate_blocked?: boolean
  competency_gate_message?: string
}

export interface EngineerProfile {
  id: number
  external_id: string
  user_id?: number | null
  display_name?: string | null
  pams_technician_id?: number | null
  employee_number?: string
  job_title?: string
  department?: string
  site?: string
  is_active: boolean
}

export interface EngineerCreatePayload {
  user_id?: number | null
  display_name?: string | null
  employee_number?: string
  job_title?: string
  role?: string
  department?: string
  site?: string
}

export interface PamsTechnicianSyncResult {
  created: number
  updated: number
  deactivated: number
  skipped: number
  errors: number
}

export interface CompetencyRecord {
  id: number
  engineer_id: number
  asset_type_id: number
  template_id: number
  source_type: string
  state: string
  outcome?: string
  assessed_at?: string
  expires_at?: string
}

export interface AssessmentResponseCreate {
  question_id: number
  verdict?: 'competent' | 'not_competent' | 'na'
  feedback?: string
  supervisor_notes?: string
}

export interface AssessmentResponseUpdate {
  verdict?: 'competent' | 'not_competent' | 'na'
  feedback?: string
  supervisor_notes?: string
  engineer_signature?: string
  engineer_signed_at?: string
}

export interface InductionResponseCreate {
  question_id: number
  shown_explained?: boolean
  understanding?: 'competent' | 'not_yet_competent' | 'na'
  supervisor_notes?: string
}

export interface InductionResponseUpdate {
  shown_explained?: boolean
  understanding?: 'competent' | 'not_yet_competent' | 'na'
  supervisor_notes?: string
  engineer_signature?: string
  engineer_signed_at?: string
}

export interface AssessmentResponseRecord {
  id: string
  run_id: string
  question_id: number
  verdict?: 'competent' | 'not_competent' | 'na'
  feedback?: string
  supervisor_notes?: string
  engineer_signature?: string
}

export interface InductionResponseRecord {
  id: string
  run_id: string
  question_id: number
  shown_explained: boolean
  understanding?: 'competent' | 'not_yet_competent' | 'na'
  supervisor_notes?: string
  engineer_signature?: string
}

// ============ Training Tickets (P0 spine) ============

export type TicketVerifyState =
  | 'unverified'
  | 'pending'
  | 'verified'
  | 'rejected'
  | 'expired'

export interface TrainingTicket {
  id: number
  engineer_id: number
  scheme: string
  ticket_number: string
  issuer?: string
  issued_at?: string
  expires_at?: string
  verify_state: TicketVerifyState | string
  evidence_id?: number
  notes?: string
  tenant_id: number
  created_at: string
  updated_at: string
}

export interface TrainingTicketCreate {
  engineer_id: number
  scheme: string
  ticket_number: string
  issuer?: string
  issued_at?: string
  expires_at?: string
  verify_state?: TicketVerifyState | string
  evidence_id?: number
  notes?: string
}

export interface TrainingTicketUpdate {
  scheme?: string
  ticket_number?: string
  issuer?: string
  issued_at?: string
  expires_at?: string
  verify_state?: TicketVerifyState | string
  evidence_id?: number
  notes?: string
}

/** Paginated list matching TrainingTicketListResponse. */
export interface TrainingTicketListResponse {
  items: TrainingTicket[]
  total: number
  page: number
  page_size: number
  pages: number
}

// ============ Competency Requirements (P0 spine) ============

export interface CompetencyRequirement {
  id: number
  asset_type_id: number
  template_id: number
  name: string
  description?: string
  is_mandatory: boolean
  reassessment_interval_days: number
  role_key?: string
  site?: string
  tenant_id: number
  created_at: string
  updated_at: string
}

export interface CompetencyRequirementCreate {
  asset_type_id: number
  template_id: number
  name: string
  description?: string
  is_mandatory?: boolean
  reassessment_interval_days?: number
  role_key?: string
  site?: string
}

export interface CompetencyRequirementUpdate {
  asset_type_id?: number
  template_id?: number
  name?: string
  description?: string
  is_mandatory?: boolean
  reassessment_interval_days?: number
  role_key?: string
  site?: string
}

/** Paginated list matching CompetencyRequirementListResponse. */
export interface CompetencyRequirementListResponse {
  items: CompetencyRequirement[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface CompetencyRequirementAllocateRequest {
  engineer_ids?: number[]
  match_site?: boolean
  match_role_key?: string
  due_days?: number
}

export interface CompetencyRequirementAllocateResponse {
  requirement_id: number
  created_checklist_ids: number[]
  skipped_engineer_ids: number[]
  matched_engineer_ids: number[]
}

export type WdpSummary = {
  engineers: { total: number }
  competencies: Record<string, number>
  assessments: { total: number; completed: number }
  inductions: { total: number; completed: number }
}

export type WdpEngineerMatrix = {
  asset_types: { id: number; name: string; category: string }[]
  engineers: {
    engineer_id: number
    user_id: number
    employee_number: string | null
    competencies: Record<number, string>
  }[]
}

export type WdpTrends = {
  assessments_by_month: {
    month: string | null
    total: number
    passed: number
    failed: number
  }[]
  inductions_by_month: { month: string | null; total: number; completed: number }[]
}

export function createWorkforceApi(api: AxiosInstance) {
  const getWdpSummary = () => api.get<WdpSummary>('/api/v1/wdp-analytics/summary')

  const getWdpEngineerMatrix = () =>
    api.get<WdpEngineerMatrix>('/api/v1/wdp-analytics/engineer-matrix')

  const getWdpTrends = () => api.get<WdpTrends>('/api/v1/wdp-analytics/trends')

  return {
  // Assessments
  listAssessments: (params?: Record<string, unknown>) =>
    api.get<{
      items: AssessmentRun[]
      total: number
      page: number
      page_size: number
      pages: number
    }>('/api/v1/assessments/', { params }),
  getAssessment: (id: string) => api.get<AssessmentRun>(`/api/v1/assessments/${id}`),
  createAssessment: (data: unknown) => api.post<AssessmentRun>('/api/v1/assessments/', data),
  startAssessment: (id: string) => api.post<AssessmentRun>(`/api/v1/assessments/${id}/start`),
  completeAssessment: (id: string) => api.post<AssessmentRun>(`/api/v1/assessments/${id}/complete`),
  updateAssessment: (id: string, data: Record<string, unknown>) =>
    api.patch<AssessmentRun>(`/api/v1/assessments/${id}`, data),
  createAssessmentResponse: (runId: string, data: AssessmentResponseCreate) =>
    api.post<AssessmentResponseRecord>(`/api/v1/assessments/${runId}/responses`, data),
  updateAssessmentResponse: (responseId: string, data: AssessmentResponseUpdate) =>
    api.patch<AssessmentResponseRecord>(`/api/v1/assessments/responses/${responseId}`, data),

  // Inductions
  listInductions: (params?: Record<string, unknown>) =>
    api.get<{
      items: InductionRun[]
      total: number
      page: number
      page_size: number
      pages: number
    }>('/api/v1/inductions/', { params }),
  getInduction: (id: string) => api.get<InductionRun>(`/api/v1/inductions/${id}`),
  createInduction: (data: unknown) => api.post<InductionRun>('/api/v1/inductions/', data),
  startInduction: (id: string) => api.post<InductionRun>(`/api/v1/inductions/${id}/start`),
  completeInduction: (id: string) => api.post<InductionRun>(`/api/v1/inductions/${id}/complete`),
  updateInduction: (id: string, data: Record<string, unknown>) =>
    api.patch<InductionRun>(`/api/v1/inductions/${id}`, data),
  createInductionResponse: (runId: string, data: InductionResponseCreate) =>
    api.post<InductionResponseRecord>(`/api/v1/inductions/${runId}/responses`, data),
  updateInductionResponse: (responseId: string, data: InductionResponseUpdate) =>
    api.patch<InductionResponseRecord>(`/api/v1/inductions/responses/${responseId}`, data),

  // Engineers
  listEngineers: (params?: Record<string, unknown>) =>
    api.get<{
      items: EngineerProfile[]
      total: number
      page: number
      page_size: number
      pages: number
    }>('/api/v1/engineers/', { params }),
  getEngineer: (id: number) => api.get<EngineerProfile>(`/api/v1/engineers/${id}`),
  createEngineer: (data: EngineerCreatePayload) =>
    api.post<EngineerProfile>('/api/v1/engineers/', data),
  syncFromPams: (params?: { tenant_id?: number }) =>
    api.post<PamsTechnicianSyncResult>('/api/v1/engineers/sync-from-pams', undefined, { params }),
  getCompetencies: (engineerId: number) =>
    api.get<CompetencyRecord[]>(`/api/v1/engineers/${engineerId}/competencies`),

  // Assets
  listAssetTypes: () => api.get<{ items: AssetType[] }>('/api/v1/assets/asset-types'),
  listAssets: (params?: Record<string, unknown>) =>
    api.get<{ items: Asset[]; total: number }>('/api/v1/assets/', { params }),

  // WDP Analytics (back-compat flat methods)
  getWdpSummary,
  getWdpEngineerMatrix,
  getWdpTrends,

  /** Namespaced analytics — aliases of getWdpSummary / getWdpEngineerMatrix / getWdpTrends. */
  analytics: {
    getSummary: getWdpSummary,
    getEngineerMatrix: getWdpEngineerMatrix,
    getTrends: getWdpTrends,
  },

  // Training tickets — /api/v1/training-tickets/
  trainingTickets: {
    list: (params?: Record<string, unknown>) =>
      api.get<TrainingTicketListResponse>('/api/v1/training-tickets/', { params }),
    get: (id: number) => api.get<TrainingTicket>(`/api/v1/training-tickets/${id}`),
    create: (data: TrainingTicketCreate) =>
      api.post<TrainingTicket>('/api/v1/training-tickets/', data),
    update: (id: number, data: TrainingTicketUpdate) =>
      api.patch<TrainingTicket>(`/api/v1/training-tickets/${id}`, data),
    delete: (id: number) => api.delete(`/api/v1/training-tickets/${id}`),
  },

  // Competency requirements — /api/v1/competency-requirements/
  competencyRequirements: {
    list: (params?: Record<string, unknown>) =>
      api.get<CompetencyRequirementListResponse>('/api/v1/competency-requirements/', {
        params,
      }),
    get: (id: number) =>
      api.get<CompetencyRequirement>(`/api/v1/competency-requirements/${id}`),
    create: (data: CompetencyRequirementCreate) =>
      api.post<CompetencyRequirement>('/api/v1/competency-requirements/', data),
    update: (id: number, data: CompetencyRequirementUpdate) =>
      api.patch<CompetencyRequirement>(`/api/v1/competency-requirements/${id}`, data),
    allocate: (id: number, data: CompetencyRequirementAllocateRequest) =>
      api.post<CompetencyRequirementAllocateResponse>(
        `/api/v1/competency-requirements/${id}/allocate`,
        data,
      ),
  },
}
}
