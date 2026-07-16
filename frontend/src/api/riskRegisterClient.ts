/**
 * Risk Register API client extracted from `client.ts` (WCS-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'
import {
  riskRegisterBowtieElementPath,
  riskRegisterBowtieElementsPath,
  riskRegisterKriValuePath,
} from './riskRegisterPaths'

/** Minimal paginated shape used by risk-register list responses. */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip?: number
  limit?: number
  page?: number
  pages?: number
}

export interface RiskEntry {
  id: number
  reference?: string
  title: string
  description?: string
  category?: string
  department?: string
  risk_owner?: string
  status: string
  likelihood?: number
  impact?: number
  risk_score?: number
  residual_likelihood?: number
  residual_impact?: number
  residual_score?: number
  treatment_strategy?: string
  treatment_plan?: string
  review_date?: string
  next_review_date?: string
  created_at: string
  updated_at?: string
  risk_owner_name?: string
  review_frequency_days?: number
  inherent_likelihood?: number
  inherent_impact?: number
  inherent_score?: number
  is_within_appetite?: boolean
  is_escalated?: boolean
  escalation_reason?: string
  linked_audits?: string[]
  linked_actions?: string[]
  linked_incidents?: string[]
  /** pending | accepted | rejected — import-sourced suggestions only */
  suggestion_triage_status?: string | null
}

export interface RiskHeatmapCell {
  likelihood: number
  impact: number
  score: number
  level: string
  color: string
  risk_count: number
  risk_ids: number[]
  risk_ids_truncated?: boolean
  risk_titles: string[]
  owners_sample?: string[]
  overdue_count?: number
  outside_appetite_count?: number
  intensity?: number
  above_appetite_band?: boolean
  movers?: Array<{
    id: number
    title: string
    from: [number, number]
    to: [number, number]
    inherent_score?: number
    residual_score?: number
  }>
  /** Legacy flat-cell compat */
  count?: number
  risks?: { id: number; title: string }[]
}

export interface RiskHeatmapData {
  matrix: RiskHeatmapCell[][]
  cells?: RiskHeatmapCell[]
  summary: {
    total_risks: number
    critical_risks: number
    high_risks: number
    medium_risks?: number
    low_risks?: number
    outside_appetite: number
    average_inherent_score: number
    average_residual_score: number
  }
  likelihood_labels: Record<number, string>
  impact_labels: Record<number, string>
  score_type?: string
  view_mode?: string
  filters_applied?: Record<string, string | null | undefined>
  appetite_overlay?: { threshold: number; source: string }
}

export interface RiskSummary {
  total_risks: number
  critical?: number
  high?: number
  medium?: number
  low?: number
  by_level?: {
    critical?: number
    high?: number
    medium?: number
    low?: number
  }
  outside_appetite?: number
  overdue_review?: number
  escalated?: number
  by_category: Record<string, number>
  filters_applied?: Record<string, string | null | undefined>
}

export interface RiskTrendsResponse {
  series?: Array<{
    month: string
    avg_residual: number
    avg_inherent?: number
    assessment_count?: number
  }>
  top_movers?: Array<{
    id: number
    title: string
    from_score: number
    to_score: number
    delta: number
  }>
}

export function createRiskRegisterApi(api: AxiosInstance) {
  return {
    list: (params?: {
      skip?: number
      limit?: number
      status?: string
      category?: string
      department?: string
      search?: string
      residual_likelihood?: number
      residual_impact?: number
      inherent_likelihood?: number
      inherent_impact?: number
      outside_appetite?: boolean
      /** pending = import triage queue; all = no triage filter; omit = hide pending */
      suggestion_triage?: 'pending' | 'all'
    }) => {
      const sp = new URLSearchParams()
      if (params?.skip != null) sp.set('skip', String(params.skip))
      if (params?.limit != null) sp.set('limit', String(params.limit))
      if (params?.status) sp.set('status', params.status)
      if (params?.category) sp.set('category', params.category)
      if (params?.department) sp.set('department', params.department)
      if (params?.search) sp.set('search', params.search)
      if (params?.residual_likelihood != null)
        sp.set('residual_likelihood', String(params.residual_likelihood))
      if (params?.residual_impact != null) sp.set('residual_impact', String(params.residual_impact))
      if (params?.inherent_likelihood != null)
        sp.set('inherent_likelihood', String(params.inherent_likelihood))
      if (params?.inherent_impact != null) sp.set('inherent_impact', String(params.inherent_impact))
      if (params?.outside_appetite != null)
        sp.set('outside_appetite', String(params.outside_appetite))
      if (params?.suggestion_triage) sp.set('suggestion_triage', params.suggestion_triage)
      return api.get<PaginatedResponse<RiskEntry>>(`/api/v1/risk-register/?${sp}`)
    },
    create: (data: Partial<RiskEntry>) => api.post<RiskEntry>('/api/v1/risk-register/', data),
    get: (id: number) => api.get<RiskEntry>(`/api/v1/risk-register/${id}`),
    update: (id: number, data: Partial<RiskEntry>) =>
      api.put<RiskEntry>(`/api/v1/risk-register/${id}`, data),
    delete: (id: number) => api.delete<void>(`/api/v1/risk-register/${id}`),
    assess: (id: number, scores: { likelihood: number; impact: number }) =>
      api.post<RiskEntry>(`/api/v1/risk-register/${id}/assess`, scores),
    resolveSuggestionTriage: (
      id: number,
      body: { decision: 'accept' | 'reject'; notes?: string },
    ) =>
      api.post<{
        id: number
        reference: string
        suggestion_triage_status: string | null
        status: string
      }>(`/api/v1/risk-register/${id}/suggestion-triage`, body),
    getHeatmap: (params?: {
      category?: string
      department?: string
      status?: string
      score_type?: 'residual' | 'inherent' | 'delta'
    }) => {
      const sp = new URLSearchParams()
      if (params?.category) sp.set('category', params.category)
      if (params?.department) sp.set('department', params.department)
      if (params?.status) sp.set('status', params.status)
      if (params?.score_type) sp.set('score_type', params.score_type)
      const q = sp.toString()
      return api.get<RiskHeatmapData>(`/api/v1/risk-register/heatmap${q ? `?${q}` : ''}`)
    },
    getSummary: (params?: { category?: string; department?: string; status?: string }) => {
      const sp = new URLSearchParams()
      if (params?.category) sp.set('category', params.category)
      if (params?.department) sp.set('department', params.department)
      if (params?.status) sp.set('status', params.status)
      const q = sp.toString()
      return api.get<RiskSummary>(`/api/v1/risk-register/summary${q ? `?${q}` : ''}`)
    },
    getTrends: (days = 90, includeMovers = false) =>
      api.get<RiskTrendsResponse | RiskTrendsResponse['series']>(
        `/api/v1/risk-register/trends?days=${days}${includeMovers ? '&include_movers=true' : ''}`,
      ),
    getBowtie: (id: number) => api.get<unknown>(`/api/v1/risk-register/${id}/bowtie`),
    addBowtieElement: (id: number, data: Record<string, unknown>) =>
      api.post<unknown>(riskRegisterBowtieElementsPath(id), data),
    deleteBowtieElement: (id: number, elementId: number) =>
      api.delete<void>(riskRegisterBowtieElementPath(id, elementId)),
    listControls: () => api.get<unknown[]>('/api/v1/risk-register/controls'),
    createControl: (data: Record<string, unknown>) =>
      api.post<unknown>('/api/v1/risk-register/controls', data),
    linkControl: (riskId: number, controlId: number) =>
      api.post<void>(`/api/v1/risk-register/${riskId}/controls/${controlId}`),
    getKRIDashboard: () => api.get<unknown>('/api/v1/risk-register/kris/dashboard'),
    createKRI: (data: Record<string, unknown>) =>
      api.post<unknown>('/api/v1/risk-register/kris', data),
    updateKRIValue: (id: number, value: number) =>
      api.put<unknown>(riskRegisterKriValuePath(id), { value }),
    getKRIHistory: (id: number) => api.get<unknown>(`/api/v1/risk-register/kris/${id}/history`),
    getAppetiteStatements: () => api.get<unknown[]>('/api/v1/risk-register/appetite/statements'),
  }
}
