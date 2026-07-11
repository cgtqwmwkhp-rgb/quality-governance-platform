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
  title?: string
  location?: string
  status: string
  outcome?: string
  scheduled_date?: string
  started_at?: string
  completed_at?: string
  created_at: string
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
}

export interface EngineerProfile {
  id: number
  external_id: string
  user_id: number
  employee_number?: string
  job_title?: string
  department?: string
  site?: string
  is_active: boolean
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

export function createWorkforceApi(api: AxiosInstance) {
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
  getCompetencies: (engineerId: number) =>
    api.get<CompetencyRecord[]>(`/api/v1/engineers/${engineerId}/competencies`),

  // Assets
  listAssetTypes: () => api.get<{ items: AssetType[] }>('/api/v1/assets/asset-types'),
  listAssets: (params?: Record<string, unknown>) =>
    api.get<{ items: Asset[]; total: number }>('/api/v1/assets/', { params }),

  // WDP Analytics
  getWdpSummary: () =>
    api.get<{
      engineers: { total: number }
      competencies: Record<string, number>
      assessments: { total: number; completed: number }
      inductions: { total: number; completed: number }
    }>('/api/v1/wdp-analytics/summary'),

  getWdpEngineerMatrix: () =>
    api.get<{
      asset_types: { id: number; name: string; category: string }[]
      engineers: {
        engineer_id: number
        user_id: number
        employee_number: string | null
        competencies: Record<number, string>
      }[]
    }>('/api/v1/wdp-analytics/engineer-matrix'),

  getWdpTrends: () =>
    api.get<{
      assessments_by_month: {
        month: string | null
        total: number
        passed: number
        failed: number
      }[]
      inductions_by_month: { month: string | null; total: number; completed: number }[]
    }>('/api/v1/wdp-analytics/trends'),
}
}
