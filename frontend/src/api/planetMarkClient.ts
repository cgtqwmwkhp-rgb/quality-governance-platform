/**
 * Planet Mark / carbon API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'
import type { SetupRequiredResponse } from '../components/ui/SetupRequiredPanel'

// ============ Planet Mark Types ============

export interface CarbonReportingYear {
  id: number
  year: number
  baseline_year: boolean
  total_emissions_tco2e: number
  scope1_emissions: number
  scope2_emissions: number
  scope3_emissions: number
  reduction_target_pct?: number
  status: 'draft' | 'in_progress' | 'submitted' | 'verified'
  certification_status?: string
  created_at: string
}

export interface PlanetMarkDashboardResponse {
  current_year: {
    id: number
    label: string
    total_emissions: number
    emissions_per_fte: number
    fte: number
    yoy_change_percent: number | null
    on_track: boolean
  }
  emissions_breakdown: {
    scope_1: { value: number; label: string }
    scope_2: { value: number; label: string }
    scope_3: { value: number; label: string }
  }
  data_quality: {
    scope_1_2: number
    scope_3: number
    target: number
  }
  certification: {
    status: string
    expiry_date: string | null
  }
  actions: {
    total: number
    completed: number
    overdue: number
  }
  targets: {
    reduction_percent: number | null
    target_per_fte: number | null
  }
  historical_years: { label: string; total: number; per_fte: number }[]
}

export interface PlanetMarkReportingYearRecord {
  id: number
  year_label: string
  year_number: number
  period: string
  average_fte: number
  total_emissions: number
  emissions_per_fte: number
  scope_1: number
  scope_2_market: number
  scope_3: number
  data_quality: number
  certification_status: string
  is_baseline: boolean
}

export interface PlanetMarkReportingYearsResponse {
  total: number
  years: PlanetMarkReportingYearRecord[]
}

export interface PlanetMarkEmissionSourceRecord {
  id: number
  source_name: string
  source_category: string
  scope: string
  activity_value: number
  activity_unit: string
  co2e_tonnes: number
  percentage: number
  data_quality: string
}

export interface PlanetMarkEmissionSourcesResponse {
  year_id: number
  total_co2e: number
  sources: PlanetMarkEmissionSourceRecord[]
}

export interface PlanetMarkScope3CategoryRecord {
  number: number
  name: string
  description?: string
  is_relevant?: boolean
  is_measured: boolean
  total_co2e: number
  percentage: number
  data_quality_score?: number | null
  calculation_method?: string | null
  exclusion_reason?: string | null
}

export interface PlanetMarkScope3Response {
  year_id: number
  measured_count: number
  total_measured?: number
  total_co2e: number
  categories: PlanetMarkScope3CategoryRecord[]
}

export interface PlanetMarkActionRecord {
  id: number
  action_id: string
  action_title: string
  owner: string
  deadline: string
  scheduled_month: string
  status: string
  progress_percent: number
  target_scope?: string | null
  expected_reduction_pct?: number | null
  is_overdue: boolean
}

export interface PlanetMarkActionsResponse {
  year_id: number
  summary: {
    total: number
    completed: number
    in_progress: number
    overdue: number
    completion_rate: number
  }
  actions: PlanetMarkActionRecord[]
}

export interface PlanetMarkCertificationResponse {
  year_id: number
  year_label: string
  status: string
  certificate_number: string | null
  certification_date: string | null
  expiry_date: string | null
  readiness_percent: number
  evidence_checklist: Array<{
    type: string
    category: string
    description: string
    required: boolean
    uploaded: boolean
    verified: boolean
  }>
  actions_completed: number
  actions_total: number
  data_quality_met: boolean
  next_steps: string[]
}

export interface PlanetMarkDataQualityResponse {
  year_id: number
  overall_score: number
  max_score: number
  scopes: Record<
    string,
    { score: number; actual_pct: number; source_count?: number; recommendations: string[] }
  >
  priority_improvements: Array<{ action: string; impact: string }>
  target_scores: Record<string, string>
}

export interface PlanetMarkEvidenceRecord {
  id: number
  document_name: string
  document_type: string
  evidence_category: string
  period_covered: string | null
  file_size_kb: number | null
  mime_type: string | null
  is_verified: boolean
  verified_by: string | null
  linked_action_id: number | null
  notes: string | null
  uploaded_by: string | null
  uploaded_at: string
  storage_key: string | null
}

export interface PlanetMarkEvidenceListResponse {
  total: number
  evidence: PlanetMarkEvidenceRecord[]
}

/**
 * Planet Mark Carbon Management API client.
 * Endpoints: /api/v1/planet-mark/*
 */
export function createPlanetMarkApi(api: AxiosInstance) {
  return {
  /**
   * Get carbon management dashboard summary.
   */
  getDashboard: () =>
    api.get<PlanetMarkDashboardResponse | SetupRequiredResponse>('/api/v1/planet-mark/dashboard'),

  /**
   * List all carbon reporting years.
   */
  listYears: () =>
    api.get<PlanetMarkReportingYearsResponse | SetupRequiredResponse>('/api/v1/planet-mark/years'),

  /**
   * Create a carbon reporting year for first-time module setup.
   */
  createReportingYear: (data: {
    year_label: string
    year_number: number
    period_start: string
    period_end: string
    average_fte: number
    organization_name?: string
    sites_included?: string[]
    is_baseline_year?: boolean
    reduction_target_percent?: number
  }) =>
    api.post<{ id: number; year_label: string; message: string }>(
      '/api/v1/planet-mark/years',
      data,
    ),

  /**
   * Get detailed data for a specific reporting year.
   */
  getYear: (yearId: number) => api.get<CarbonReportingYear>(`/api/v1/planet-mark/years/${yearId}`),

  /**
   * List emission sources for a year.
   */
  listSources: (yearId: number, scope?: string) => {
    const sp = new URLSearchParams()
    if (scope) sp.set('scope', scope)
    const query = sp.toString()
    return api.get<PlanetMarkEmissionSourcesResponse>(
      `/api/v1/planet-mark/years/${yearId}/sources${query ? `?${query}` : ''}`,
    )
  },

  /**
   * Get Scope 3 category breakdown for a year.
   */
  getScope3: (yearId: number) =>
    api.get<PlanetMarkScope3Response>(`/api/v1/planet-mark/years/${yearId}/scope3`),

  /**
   * List improvement actions for a year.
   */
  listActions: (yearId: number) =>
    api.get<PlanetMarkActionsResponse>(`/api/v1/planet-mark/years/${yearId}/actions`),

  /**
   * Get certification status for a year.
   */
  getCertification: (yearId: number) =>
    api.get<PlanetMarkCertificationResponse>(`/api/v1/planet-mark/years/${yearId}/certification`),

  /**
   * Get the data quality assessment for a reporting year.
   */
  getDataQuality: (yearId: number) =>
    api.get<PlanetMarkDataQualityResponse>(`/api/v1/planet-mark/years/${yearId}/data-quality`),

  /**
   * Add an emission source to a reporting year.
   */
  addEmissionSource: (
    yearId: number,
    data: {
      source_name: string
      source_category: string
      scope: string
      activity_type: string
      activity_value: number
      activity_unit: string
      data_quality_level?: string
      data_source?: string
    },
  ) =>
    api.post<{ id: number; co2e_tonnes: number; message: string }>(
      `/api/v1/planet-mark/years/${yearId}/sources`,
      data,
    ),

  /**
   * Create a SMART improvement action for a reporting year.
   */
  createAction: (
    yearId: number,
    data: {
      action_title: string
      specific: string
      measurable: string
      achievable_owner: string
      time_bound: string
      expected_reduction_pct?: number
    },
  ) =>
    api.post<{ id: number; action_id: string; message: string }>(
      `/api/v1/planet-mark/years/${yearId}/actions`,
      data,
    ),

  /**
   * Update an improvement action's status, progress, and notes.
   */
  updateAction: (
    yearId: number,
    actionId: number,
    data: { status?: string; progress_percent?: number; notes?: string },
  ) =>
    api.put<{ message: string; id: number }>(
      `/api/v1/planet-mark/years/${yearId}/actions/${actionId}`,
      data,
    ),

  /**
   * Bulk-update status for multiple actions.
   */
  bulkUpdateActions: (yearId: number, actionIds: number[], status: string) =>
    api.post<{ updated_count: number; updated_ids: number[] }>(
      `/api/v1/planet-mark/years/${yearId}/actions/bulk-status`,
      { action_ids: actionIds, status },
    ),

  /**
   * Get KPI summary for improvement actions dashboard.
   */
  getActionsSummary: (yearId: number) =>
    api.get<{
      year_id: number
      total: number
      completed: number
      in_progress: number
      overdue: number
      not_started: number
      completion_rate_percent: number
      avg_progress_percent: number
    }>(`/api/v1/planet-mark/years/${yearId}/actions/summary`),

  /**
   * Update certification status (state-machine guarded).
   */
  patchCertification: (
    yearId: number,
    data: {
      status: string
      certificate_number?: string
      certification_date?: string
      expiry_date?: string
      certifying_body?: string
      assessor_name?: string
      assessment_notes?: string
    },
  ) =>
    api.patch<{ message: string; status: string }>(
      `/api/v1/planet-mark/years/${yearId}/certification`,
      data,
    ),

  /**
   * List evidence documents for a reporting year.
   */
  listEvidence: (yearId: number, params?: { document_type?: string; linked_action_id?: number }) => {
    const sp = new URLSearchParams()
    if (params?.document_type) sp.set('document_type', params.document_type)
    if (params?.linked_action_id) sp.set('linked_action_id', String(params.linked_action_id))
    const query = sp.toString()
    return api.get<PlanetMarkEvidenceListResponse>(
      `/api/v1/planet-mark/years/${yearId}/evidence${query ? `?${query}` : ''}`,
    )
  },

  /**
   * Upload an evidence document (multipart/form-data).
   */
  uploadEvidence: (yearId: number, formData: FormData) =>
    api.post<{
      id: number
      document_name: string
      storage_key: string | null
      file_hash: string
      message: string
      duplicate: boolean
    }>(`/api/v1/planet-mark/years/${yearId}/evidence/upload`, formData, {
      timeout: 120_000,
    }),

  /**
   * Verify or annotate an evidence document.
   */
  patchEvidence: (
    yearId: number,
    evidenceId: number,
    data: { is_verified?: boolean; verified_by?: string; notes?: string },
  ) =>
    api.patch<{ message: string; id: number }>(
      `/api/v1/planet-mark/years/${yearId}/evidence/${evidenceId}`,
      data,
    ),

  /**
   * Delete an evidence document.
   */
  deleteEvidence: (yearId: number, evidenceId: number) =>
    api.delete<{ message: string; id: number }>(
      `/api/v1/planet-mark/years/${yearId}/evidence/${evidenceId}`,
    ),

  /**
   * Get a signed download URL for an evidence document.
   */
  getEvidenceDownloadUrl: (yearId: number, evidenceId: number) =>
    api.get<{
      id: number
      document_name: string
      url: string
      expires_in_seconds: number
    }>(`/api/v1/planet-mark/years/${yearId}/evidence/${evidenceId}/download`),

  /**
   * Upload and AI-extract actions from an action plan document.
   */
  extractActionPlan: (yearId: number, formData: FormData) =>
    api.post<{
      session_id: string
      year_id: number
      source_filename: string
      extracted_count: number
      rows: Array<{
        action_title: string
        description: string
        owner: string
        deadline: string | null
        category: string
        expected_reduction_pct: number
        confidence: number
        needs_review: boolean
      }>
      extraction_method: string
      warnings: string[]
    }>(`/api/v1/planet-mark/years/${yearId}/actions/import/extract`, formData),

  /**
   * Confirm and persist selected extracted actions.
   */
  confirmActionImport: (
    yearId: number,
    sessionId: string,
    selectedIndices?: number[],
  ) =>
    api.post<{ message: string; created_count: number; action_ids: string[] }>(
      `/api/v1/planet-mark/years/${yearId}/actions/import/confirm`,
      { session_id: sessionId, selected_indices: selectedIndices ?? null },
    ),

  /**
   * Apply an imported Planet Mark audit report to the carbon dashboard.
   * Triggers sync of extracted carbon data into CarbonReportingYear domain.
   */
  applyImport: (importJobId: number, reportingYearId?: number) =>
    api.post<{
      status: string
      year_id: number | null
      year_label: string | null
      created_year: boolean
      sources_created: number
      actions_created: number
      detail: string | null
    }>('/api/v1/planet-mark/apply-import', {
      import_job_id: importJobId,
      reporting_year_id: reportingYearId ?? null,
    }),

  /**
   * Get the Planet Mark carbon sync status for a specific import job.
   */
  getImportSyncStatus: (importJobId: number) =>
    api.get<{
      import_job_id: number
      detected_scheme: string
      status: string
      planet_mark_sync_status: string
      planet_mark_sync_detail: Record<string, unknown>
      has_carbon_data: boolean
      retry_available: boolean
    }>(`/api/v1/planet-mark/import-status/${importJobId}`),
  }
}
