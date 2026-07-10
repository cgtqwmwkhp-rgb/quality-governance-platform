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
  /** pending | accepted | rejected — import-sourced suggestions only */
  suggestion_triage_status?: string | null
}

export interface RiskHeatmapData {
  cells: {
    likelihood: number
    impact: number
    count: number
    risks: { id: number; title: string }[]
  }[]
}

export interface RiskSummary {
  total_risks: number
  critical: number
  high: number
  medium: number
  low: number
  by_category: Record<string, number>
}

export function createRiskRegisterApi(api: AxiosInstance) {
  return {
    list: (params?: {
      skip?: number
      limit?: number
      status?: string
      category?: string
      search?: string
      /** pending = import triage queue; all = no triage filter; omit = hide pending */
      suggestion_triage?: 'pending' | 'all'
    }) => {
      const sp = new URLSearchParams()
      if (params?.skip != null) sp.set('skip', String(params.skip))
      if (params?.limit != null) sp.set('limit', String(params.limit))
      if (params?.status) sp.set('status', params.status)
      if (params?.category) sp.set('category', params.category)
      if (params?.search) sp.set('search', params.search)
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
    getHeatmap: () => api.get<RiskHeatmapData>('/api/v1/risk-register/heatmap'),
    getSummary: () => api.get<RiskSummary>('/api/v1/risk-register/summary'),
    getTrends: (days = 90) => api.get<unknown>(`/api/v1/risk-register/trends?days=${days}`),
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
