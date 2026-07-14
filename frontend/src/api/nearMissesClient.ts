/**
 * Near-misses API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'
import type { Investigation } from './investigationsClient'
import type { RunningSheetEntry } from './incidentsClient'

/** Minimal paginated shape used by near-miss list responses. */
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

// ============ Near Miss Types ============
export interface NearMiss {
  id: number
  reference_number: string
  reporter_name: string
  reporter_email?: string
  reporter_phone?: string
  reporter_role?: string
  was_involved: boolean
  contract: string
  contract_other?: string
  location: string
  location_coordinates?: string
  event_date: string
  event_time?: string
  description: string
  potential_consequences?: string
  preventive_action_suggested?: string
  persons_involved?: string
  witnesses_present: boolean
  witness_names?: string
  asset_number?: string
  asset_type?: string
  /** Linked Asset registry id (golden thread). Legacy asset_number/asset_type retained. */
  asset_id?: number | null
  risk_category?: string
  potential_severity?: string
  /** Comma-separated risk register IDs linked from this near miss. */
  linked_risk_ids?: string
  status: string
  priority: string
  assigned_to_id?: number
  assigned_at?: string
  resolution_notes?: string
  corrective_actions_taken?: string
  closed_at?: string
  created_at: string
  updated_at: string
}

export interface NearMissCreate {
  reporter_name: string
  reporter_email?: string
  reporter_phone?: string
  reporter_role?: string
  was_involved?: boolean
  contract: string
  contract_other?: string
  location: string
  location_coordinates?: string
  event_date: string
  event_time?: string
  description: string
  potential_consequences?: string
  preventive_action_suggested?: string
  persons_involved?: string
  witnesses_present?: boolean
  witness_names?: string
  asset_number?: string
  asset_type?: string
  asset_id?: number | null
  risk_category?: string
  potential_severity?: string
}

export interface NearMissUpdate {
  description?: string
  potential_consequences?: string
  preventive_action_suggested?: string
  status?: string
  priority?: string
  assigned_to_id?: number
  resolution_notes?: string
  corrective_actions_taken?: string
  risk_category?: string
  potential_severity?: string
  asset_id?: number | null
  asset_number?: string
  asset_type?: string
}

export interface RaiseRiskFromNearMissRequest {
  title?: string
  description?: string
  likelihood?: number
  impact?: number
  category?: string
  treatment_strategy?: string
}

export interface RaiseRiskFromNearMissResponse {
  risk: {
    id: number
    reference_number: string
    title: string
    risk_source?: string | null
  }
  near_miss_id: number
  linked_risk_ids: string
  near_miss_href: string
  risk_register_href: string
}

export function createNearMissesApi(api: AxiosInstance) {
  return {
    list: (page = 1, pageSize = 10) =>
      api.get<PaginatedResponse<NearMiss>>(
        `/api/v1/near-misses/?page=${page}&page_size=${pageSize}`,
      ),
    create: (data: NearMissCreate) => api.post<NearMiss>('/api/v1/near-misses/', data),
    get: (id: number) => api.get<NearMiss>(`/api/v1/near-misses/${id}`),
    update: (id: number, data: NearMissUpdate) =>
      api.patch<NearMiss>(`/api/v1/near-misses/${id}`, data),
    raiseRisk: (id: number, data?: RaiseRiskFromNearMissRequest) =>
      api.post<RaiseRiskFromNearMissResponse>(`/api/v1/near-misses/${id}/raise-risk`, data || {}),
    listInvestigations: (id: number, page = 1, pageSize = 10) =>
      api.get<PaginatedResponse<Investigation>>(
        `/api/v1/near-misses/${id}/investigations?page=${page}&page_size=${pageSize}`,
      ),
    listRunningSheet: (nearMissId: number) =>
      api.get<RunningSheetEntry[]>(`/api/v1/near-misses/${nearMissId}/running-sheet`),
    addRunningSheetEntry: (nearMissId: number, data: { content: string; entry_type?: string }) =>
      api.post<RunningSheetEntry>(`/api/v1/near-misses/${nearMissId}/running-sheet`, data),
    deleteRunningSheetEntry: (nearMissId: number, entryId: number) =>
      api.delete(`/api/v1/near-misses/${nearMissId}/running-sheet/${entryId}`),
  }
}
