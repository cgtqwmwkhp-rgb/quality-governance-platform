/**
 * Policies (controlled documents) API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

/** Minimal paginated shape used by policy list responses. */
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

// ============ Policy Types ============
export interface Policy {
  id: number
  reference_number: string
  title: string
  description?: string
  document_type: string
  status: string
  category?: string
  department?: string
  review_frequency_months: number
  next_review_date?: string
  is_public: boolean
  created_at: string
}

export interface PolicyCreate {
  title: string
  description?: string
  document_type: string
  category?: string
  department?: string
  review_frequency_months?: number
}

export function createPoliciesApi(api: AxiosInstance) {
  return {
    list: (page = 1, pageSize = 10) =>
      api.get<PaginatedResponse<Policy>>(`/api/v1/policies?page=${page}&page_size=${pageSize}`),
    create: (data: PolicyCreate) => api.post<Policy>('/api/v1/policies', data),
    get: (id: number) => api.get<Policy>(`/api/v1/policies/${id}`),
  }
}
