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

/** Typed Excel Risk Card / profile shell (RR-P0). */
export interface RiskProfileAssessmentHistoryItem {
  date?: string | null
  inherent_score?: number | null
  residual_score?: number | null
  status?: string | null
}

export interface RiskProfile {
  id: number
  reference?: string | null
  title: string
  description?: string | null
  category?: string | null
  status?: string | null
  treatment?: string | null
  inherent_likelihood?: number | null
  inherent_impact?: number | null
  inherent_score?: number | null
  inherent_level?: string | null
  residual_likelihood?: number | null
  residual_impact?: number | null
  residual_score?: number | null
  residual_level?: string | null
  trend?: 'increasing' | 'stable' | 'decreasing' | null
  risk_owner_id?: number | null
  risk_owner_name?: string | null
  last_review_date?: string | null
  next_review_date?: string | null
  updated_at?: string | null
  created_at?: string | null
  assessment_history?: RiskProfileAssessmentHistoryItem[]
  linked_actions?: unknown[]
  review_notes?: string | null
}

export interface RiskAssessPayload {
  inherent_likelihood?: number
  inherent_impact?: number
  residual_likelihood?: number
  residual_impact?: number
  review_notes?: string
  assessment_notes?: string
  last_review_date?: string
  next_review_date?: string
  trend?: 'increasing' | 'stable' | 'decreasing'
}

export interface RiskAssessResponse {
  message: string
  inherent_score?: number
  residual_score?: number
  risk_level?: string
  is_within_appetite?: boolean
  trend?: 'increasing' | 'stable' | 'decreasing'
  last_review_date?: string | null
  next_review_date?: string | null
}

export interface RiskTrendPoint {
  month: string
  avg_inherent?: number
  avg_residual: number
  assessment_count?: number
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
    getProfile: (id: number) =>
      api.get<RiskProfile>(`/api/v1/risk-register/${id}/profile`),
    update: (id: number, data: Partial<RiskEntry>) =>
      api.put<RiskEntry>(`/api/v1/risk-register/${id}`, data),
    delete: (id: number) => api.delete<void>(`/api/v1/risk-register/${id}`),
    assess: (id: number, data: RiskAssessPayload) =>
      api.post<RiskAssessResponse>(`/api/v1/risk-register/${id}/assess`, data),
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
    getTrends: (days = 90, includeMovers = false, riskId?: number) => {
      const sp = new URLSearchParams({ days: String(days) })
      if (includeMovers) sp.set('include_movers', 'true')
      if (riskId != null) sp.set('risk_id', String(riskId))
      return api.get<RiskTrendsResponse | RiskTrendPoint[]>(
        `/api/v1/risk-register/trends?${sp.toString()}`,
      )
    },
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
