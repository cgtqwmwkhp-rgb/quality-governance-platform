import type { AxiosInstance } from 'axios'

export interface SafetyInsightCaseRef {
  module: string
  id: number
  reference_number: string
}

export interface SafetyInsightTheme {
  id: number
  label: string
  rationale?: string | null
  module_scope?: string | null
  case_count: number
  share?: number | null
  velocity?: string | null
  severity_overlay?: string | null
  case_refs: SafetyInsightCaseRef[]
}

export interface SafetyInsightDimension {
  id: number
  dimension_type: string
  dimension_key: string
  case_count: number
  case_refs: SafetyInsightCaseRef[]
}

export interface SafetyInsightRun {
  id: number
  status: string
  progress_pct: number
  progress_message?: string | null
  scope: string
  topic_query?: string | null
  modules: string[]
  date_from?: string | null
  date_to?: string | null
  min_cluster_size: number
  include_synthesis: boolean
  include_benchmark: boolean
  corpus_summary?: Record<string, unknown> | null
  ratios?: Record<string, unknown> | null
  quality_scorecard?: Record<string, unknown> | null
  synthesis_text?: string | null
  benchmarks?: Array<{ title?: string; summary?: string; source_url?: string | null }>
  synthesis_available: boolean
  research_available: boolean
  models_used?: Record<string, unknown> | null
  error_code?: string | null
  error_detail?: string | null
  created_at?: string | null
  completed_at?: string | null
  micro_themes?: SafetyInsightTheme[]
  dimensions?: SafetyInsightDimension[]
}

export interface DeepRunCreatePayload {
  modules: string[]
  scope: 'org' | 'topic'
  topic_query?: string
  date_from?: string
  date_to?: string
  min_cluster_size: number
  include_synthesis: boolean
  include_benchmark: boolean
}

export function createSafetyInsightsApi(api: AxiosInstance) {
  return {
    startRun: (payload: DeepRunCreatePayload) =>
      api.post<SafetyInsightRun>('/api/v1/safety-insights/runs', payload),
    getRun: (runId: number) => api.get<SafetyInsightRun>(`/api/v1/safety-insights/runs/${runId}`),
    listRuns: (limit = 20) =>
      api.get<{ items: SafetyInsightRun[]; total: number }>('/api/v1/safety-insights/runs', {
        params: { limit },
      }),
    latest: () => api.get('/api/v1/safety-insights/latest'),
    themeCases: (themeId: number) => api.get(`/api/v1/safety-insights/themes/${themeId}/cases`),
    exportRun: (runId: number) => api.post(`/api/v1/safety-insights/runs/${runId}/export`),
  }
}
