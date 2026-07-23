/**
 * Complaints API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'
import type { Investigation } from './investigationsClient'
import type { RunningSheetEntry } from './incidentsClient'

/** Minimal paginated shape used by complaint list responses. */
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

export type ComplaintSourceType =
  | 'manual'
  | 'email'
  | 'api'
  | 'phone'
  | 'portal'
  | 'in_person'

// ============ Complaint Types ============
export interface Complaint {
  id: number
  reference_number: string
  title: string
  description: string
  complaint_type: string
  priority: string
  status: string
  received_date: string
  complainant_name: string
  complainant_email?: string
  complainant_phone?: string
  complainant_company?: string
  related_reference?: string
  department?: string
  source_type?: ComplaintSourceType | string
  contract_id?: number | null
  subject_user_id?: number | null
  subject_name?: string | null
  alleged_event_at?: string | null
  target_resolution_date?: string
  investigation_notes?: string
  root_cause?: string
  resolution_summary?: string
  lessons_learnt?: string | null
  customer_satisfied?: boolean
  compensation_offered?: string
  owner_id?: number
  reporter_submission?: Record<string, unknown> | null
  due_date?: string
  created_at: string
  updated_at?: string
  closed_at?: string | null
}

export interface ComplaintCreate {
  title: string
  description: string
  complaint_type: string
  priority: string
  received_date: string
  complainant_name: string
  complainant_email?: string
  complainant_phone?: string
  complainant_company?: string
  related_reference?: string
  department?: string
  source_type?: ComplaintSourceType
  contract_id?: number | null
  subject_user_id?: number | null
  subject_name?: string | null
  alleged_event_at?: string | null
  reporter_submission?: Record<string, unknown>
}

export interface ComplaintUpdate {
  title?: string
  description?: string
  complaint_type?: string
  priority?: string
  status?: string
  complainant_name?: string
  complainant_email?: string
  complainant_phone?: string
  complainant_company?: string
  related_reference?: string
  source_type?: ComplaintSourceType
  contract_id?: number | null
  subject_user_id?: number | null
  subject_name?: string | null
  alleged_event_at?: string | null
  received_date?: string
  investigation_notes?: string
  root_cause?: string
  customer_satisfied?: boolean
  compensation_offered?: string
  resolution_summary?: string
  lessons_learnt?: string | null
  owner_id?: number | null
}

export function createComplaintsApi(api: AxiosInstance) {
  return {
    list: (page = 1, pageSize = 10, options?: { owner?: 'unassigned' }) => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      })
      if (options?.owner) params.set('owner', options.owner)
      return api.get<PaginatedResponse<Complaint>>(`/api/v1/complaints/?${params.toString()}`)
    },
    create: (data: ComplaintCreate) => api.post<Complaint>('/api/v1/complaints/', data),
    get: (id: number) => api.get<Complaint>(`/api/v1/complaints/${id}`),
    update: (id: number, data: ComplaintUpdate) =>
      api.patch<Complaint>(`/api/v1/complaints/${id}`, data),
    listInvestigations: (id: number, page = 1, pageSize = 10) =>
      api.get<PaginatedResponse<Investigation>>(
        `/api/v1/complaints/${id}/investigations?page=${page}&page_size=${pageSize}`,
      ),
    listRunningSheet: (complaintId: number) =>
      api.get<RunningSheetEntry[]>(`/api/v1/complaints/${complaintId}/running-sheet`),
    addRunningSheetEntry: (complaintId: number, data: { content: string; entry_type?: string }) =>
      api.post<RunningSheetEntry>(`/api/v1/complaints/${complaintId}/running-sheet`, data),
    deleteRunningSheetEntry: (complaintId: number, entryId: number) =>
      api.delete(`/api/v1/complaints/${complaintId}/running-sheet/${entryId}`),
  }
}
