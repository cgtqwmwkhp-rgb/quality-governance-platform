/**
 * Standards API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

/** Minimal paginated shape used by standards list responses. */
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

export interface Standard {
  id: number
  code: string
  name: string
  full_name: string
  version: string
  description?: string
  is_active: boolean
  created_at: string
}

export interface Clause {
  id: number
  standard_id: number
  clause_number: string
  title: string
  description?: string
  parent_clause_id?: number | null
  level: number
  is_active: boolean
}

export interface ControlListItem {
  id: number
  clause_id: number
  clause_number: string
  control_number: string
  title: string
  implementation_status?: string
  is_applicable: boolean
  is_active: boolean
}

export interface ComplianceScore {
  standard_id: number
  standard_code: string
  total_controls: number
  implemented_count: number
  partial_count: number
  not_implemented_count: number
  compliance_percentage: number
  setup_required: boolean
}

export function createStandardsApi(api: AxiosInstance) {
  return {
    list: (page = 1, size = 10) =>
      api.get<PaginatedResponse<Standard>>(`/api/v1/standards/?page=${page}&page_size=${size}`),
    get: (id: number) => api.get<Standard & { clauses: Clause[] }>(`/api/v1/standards/${id}`),
    getClauses: (standardId: number) =>
      api.get<Clause[]>(`/api/v1/standards/${standardId}/clauses`),
    getControls: (standardId: number) =>
      api.get<ControlListItem[]>(`/api/v1/standards/${standardId}/controls`),
    getComplianceScore: (standardId: number) =>
      api.get<ComplianceScore>(`/api/v1/standards/${standardId}/compliance-score`),
  }
}
