/**
 * Incidents API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'
import type { Investigation } from './investigationsClient'

/** Minimal paginated shape used by incident list responses. */
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

// ============ Incident Types ============
export interface Incident {
  id: number
  reference_number: string
  title: string
  description: string
  incident_type: string
  severity: string
  status: string
  incident_date: string
  reported_date: string
  location?: string
  department?: string
  contract_id?: number | null
  created_at: string
  updated_at?: string
  reporter_name?: string
  reporter_email?: string
  people_involved?: string
  witnesses?: string
  immediate_actions?: string
  first_aid_given?: boolean
  emergency_services_called?: boolean
  medical_assistance?: string | null
  emergency_services?: string[] | null
  is_injury?: boolean
  body_parts?: string[] | null
  is_lti?: boolean
  days_lost?: number | null
  is_minor_injury?: boolean
  investigator_id?: number | null
  is_riddor_reportable?: boolean | null
  riddor_classification?: string | null
  riddor_rationale?: string | null
  is_sif?: boolean | null
  life_altering_potential?: boolean | null
  reporter_submission?: Record<string, unknown> | null
  closed_at?: string | null
  lessons_learnt?: string | null
  owner_id?: number | null
  /** Linked Asset registry id (golden thread). */
  asset_id?: number | null
  /** Comma-separated enterprise risk register IDs linked from this incident. */
  linked_risk_ids?: string
}

export interface IncidentCreate {
  title: string
  description: string
  incident_type: string
  severity: string
  incident_date: string
  reported_date: string
  location?: string
  department?: string
  contract_id?: number | null
  reporter_email?: string
  reporter_name?: string
  asset_id?: number | null
  is_injury?: boolean
  body_parts?: string[] | null
  is_lti?: boolean
  days_lost?: number | null
  is_minor_injury?: boolean
  first_aid_given?: boolean
  emergency_services_called?: boolean
  medical_assistance?: string | null
  emergency_services?: string[] | null
  people_involved?: string
  is_riddor_reportable?: boolean | null
  riddor_classification?: string | null
  riddor_rationale?: string | null
}

export interface IncidentUpdate {
  title?: string
  description?: string
  incident_type?: string
  severity?: string
  status?: string
  location?: string
  department?: string
  contract_id?: number | null
  owner_id?: number | null
  asset_id?: number | null
  is_injury?: boolean
  body_parts?: string[] | null
  is_lti?: boolean
  days_lost?: number | null
  is_minor_injury?: boolean
  first_aid_given?: boolean
  emergency_services_called?: boolean
  medical_assistance?: string | null
  emergency_services?: string[] | null
  people_involved?: string
  is_riddor_reportable?: boolean | null
  riddor_classification?: string | null
  riddor_rationale?: string | null
  lessons_learnt?: string | null
}

export interface RaiseRiskFromIncidentRequest {
  title?: string
  description?: string
  likelihood?: number
  impact?: number
  category?: string
  treatment_strategy?: string
}

export interface RaiseRiskFromIncidentResponse {
  risk: {
    id: number
    reference_number: string
    title: string
    risk_source?: string | null
  }
  incident_id: number
  linked_risk_ids: string
  incident_href: string
  risk_register_href: string
}

/** Shared running-sheet entry used by incidents and sibling case modules. */
export interface RunningSheetEntry {
  id: number
  content: string
  entry_type: string
  author_id?: number
  author_email?: string
  created_at: string
}

export function createIncidentsApi(api: AxiosInstance) {
  return {
    list: (page = 1, pageSize = 10, options?: { owner?: 'unassigned' }) => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      })
      if (options?.owner) params.set('owner', options.owner)
      return api.get<PaginatedResponse<Incident>>(`/api/v1/incidents/?${params.toString()}`)
    },
    create: (data: IncidentCreate) => api.post<Incident>('/api/v1/incidents/', data),
    get: (id: number) => api.get<Incident>(`/api/v1/incidents/${id}`),
    raiseRisk: (id: number, data?: RaiseRiskFromIncidentRequest) =>
      api.post<RaiseRiskFromIncidentResponse>(`/api/v1/incidents/${id}/raise-risk`, data || {}),
    update: (id: number, data: IncidentUpdate) =>
      api.patch<Incident>(`/api/v1/incidents/${id}`, data),
    listInvestigations: (id: number, page = 1, pageSize = 10) =>
      api.get<PaginatedResponse<Investigation>>(
        `/api/v1/incidents/${id}/investigations?page=${page}&page_size=${pageSize}`,
      ),
    listRunningSheet: (incidentId: number) =>
      api.get<RunningSheetEntry[]>(`/api/v1/incidents/${incidentId}/running-sheet`),
    addRunningSheetEntry: (incidentId: number, data: { content: string; entry_type?: string }) =>
      api.post<RunningSheetEntry>(`/api/v1/incidents/${incidentId}/running-sheet`, data),
    deleteRunningSheetEntry: (incidentId: number, entryId: number) =>
      api.delete(`/api/v1/incidents/${incidentId}/running-sheet/${entryId}`),
  }
}
