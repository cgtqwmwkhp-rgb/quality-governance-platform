/**
 * Operational risks API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

/** Minimal paginated shape used by risk list responses. */
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

// ============ Risk Types ============
export interface Risk {
  id: number
  reference_number: string
  title: string
  description: string
  category: string
  subcategory?: string
  likelihood: number
  impact: number
  risk_score: number
  risk_level: string
  status: string
  department?: string
  treatment_strategy: string
  treatment_plan?: string
  next_review_date?: string
  is_active: boolean
  created_at: string
}

export interface RiskCreate {
  title: string
  description: string
  category: string
  subcategory?: string
  likelihood: number
  impact: number
  department?: string
  treatment_strategy?: string
  treatment_plan?: string
}

export function createRisksApi(api: AxiosInstance) {
  return {
    list: (page = 1, pageSize = 10, search?: string) => {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
      if (search) params.set('search', search)
      return api.get<PaginatedResponse<Risk>>(`/api/v1/risks/?${params.toString()}`)
    },
    create: (data: RiskCreate) => api.post<Risk>('/api/v1/risks/', data),
    get: (id: number) => api.get<Risk>(`/api/v1/risks/${id}`),
  }
}
