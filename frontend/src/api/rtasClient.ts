/**
 * RTAs (road traffic collisions) API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'
import type { Investigation } from './investigationsClient'
import type { RunningSheetEntry } from './incidentsClient'

/** Minimal paginated shape used by RTA list responses. */
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

// ============ RTA Types ============
export interface ThirdParty {
  name?: string
  contact?: string
  phone?: string
  email?: string
  vehicle_reg?: string
  vehicle_make_model?: string
  damage?: string
  injured?: boolean
  injury_details?: string
  insurer?: string
  insurer_policy_number?: string
  is_at_fault?: boolean
}

export interface Witness {
  name?: string
  phone?: string
  email?: string
  statement?: string
  willing_to_provide_statement?: boolean
}

export interface RTA {
  id: number
  reference_number: string
  title: string
  description: string
  severity: string
  status: string
  collision_date: string
  reported_date: string
  location: string
  road_name?: string
  postcode?: string
  collision_time?: string
  weather_conditions?: string
  road_conditions?: string
  lighting_conditions?: string
  company_vehicle_registration?: string
  company_vehicle_make_model?: string
  company_vehicle_damage?: string
  driver_name?: string
  driver_id?: number
  driver_email?: string
  driver_statement?: string
  driver_injured: boolean
  driver_injury_details?: string
  police_attended: boolean
  police_reference?: string
  police_station?: string
  insurance_notified: boolean
  insurance_reference?: string
  insurance_notes?: string
  estimated_cost?: number
  vehicles_involved_count?: number
  cctv_available?: boolean
  cctv_location?: string
  dashcam_footage_available?: boolean
  footage_secured?: boolean
  footage_notes?: string
  third_parties?: { parties?: ThirdParty[] }
  witnesses?: string
  witnesses_structured?: { witnesses?: Witness[] }
  fault_determination?: string
  investigation_notes?: string
  root_cause?: string
  reporter_name?: string
  reporter_email?: string
  reporter_submission?: Record<string, unknown> | null
  created_at: string
  updated_at?: string
}

export interface RTACreate {
  title: string
  description: string
  severity: string
  collision_date: string
  reported_date: string
  location: string
  road_name?: string
  postcode?: string
  weather_conditions?: string
  road_conditions?: string
  company_vehicle_registration?: string
  driver_name?: string
  driver_injured?: boolean
  police_attended?: boolean
  third_parties?: { parties?: ThirdParty[] }
  reporter_name?: string
  reporter_email?: string
  reporter_submission?: Record<string, unknown>
}

export interface RTAUpdate {
  title?: string
  description?: string
  severity?: string
  status?: string
  location?: string
  road_name?: string
  postcode?: string
  collision_time?: string
  weather_conditions?: string
  road_conditions?: string
  lighting_conditions?: string
  company_vehicle_registration?: string
  company_vehicle_make_model?: string
  company_vehicle_damage?: string
  driver_name?: string
  driver_id?: number
  driver_email?: string
  driver_statement?: string
  driver_injured?: boolean
  driver_injury_details?: string
  police_attended?: boolean
  police_reference?: string
  police_station?: string
  insurance_notified?: boolean
  insurance_reference?: string
  insurance_notes?: string
  estimated_cost?: number
  vehicles_involved_count?: number
  cctv_available?: boolean
  cctv_location?: string
  dashcam_footage_available?: boolean
  footage_secured?: boolean
  footage_notes?: string
  third_parties?: { parties?: ThirdParty[] }
  witnesses?: string
  witnesses_structured?: { witnesses?: Witness[] }
  fault_determination?: string
}

export function createRtasApi(api: AxiosInstance) {
  return {
    list: (page = 1, pageSize = 10) =>
      api.get<PaginatedResponse<RTA>>(`/api/v1/rtas/?page=${page}&page_size=${pageSize}`),
    create: (data: RTACreate) => api.post<RTA>('/api/v1/rtas/', data),
    get: (id: number) => api.get<RTA>(`/api/v1/rtas/${id}`),
    update: (id: number, data: RTAUpdate) => api.patch<RTA>(`/api/v1/rtas/${id}`, data),
    listInvestigations: (id: number, page = 1, pageSize = 10) =>
      api.get<PaginatedResponse<Investigation>>(
        `/api/v1/rtas/${id}/investigations?page=${page}&page_size=${pageSize}`,
      ),
    listRunningSheet: (rtaId: number) =>
      api.get<RunningSheetEntry[]>(`/api/v1/rtas/${rtaId}/running-sheet`),
    addRunningSheetEntry: (rtaId: number, data: { content: string; entry_type?: string }) =>
      api.post<RunningSheetEntry>(`/api/v1/rtas/${rtaId}/running-sheet`, data),
    deleteRunningSheetEntry: (rtaId: number, entryId: number) =>
      api.delete(`/api/v1/rtas/${rtaId}/running-sheet/${entryId}`),
  }
}
