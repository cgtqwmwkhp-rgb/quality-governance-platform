/**
 * Compliance Schedule API client (Wave 1).
 */
import type { AxiosInstance } from 'axios'

export type ComplianceStatus = 'current' | 'due_soon' | 'overdue'

export interface ComplianceRequirement {
  id: number
  external_id: string
  tenant_id: number
  reference_number: string
  template_id?: number | null
  location_id?: number | null
  title: string
  taxonomy_id: string
  description?: string | null
  regulatory_basis?: string | null
  frequency_months?: number | null
  frequency_days?: number | null
  anchor: 'completion' | 'schedule'
  statutory: boolean
  next_due_date: string
  last_completed_at?: string | null
  owner_id?: number | null
  is_active: boolean
  status?: ComplianceStatus | null
  created_at: string
  updated_at?: string | null
}

export interface ComplianceRecord {
  id: number
  external_id: string
  tenant_id: number
  reference_number: string
  requirement_id: number
  due_date: string
  outcome: 'completed' | 'missed'
  completed_at?: string | null
  check_passed?: boolean | null
  notes?: string | null
  library_document_id?: number | null
  filing_status: string
  filing_error?: string | null
  created_at: string
  updated_at?: string | null
}

export interface CatalogueTemplate {
  id: number
  template_key: string
  title: string
  taxonomy_id: string
  description?: string | null
  regulatory_basis?: string | null
  frequency_months?: number | null
  frequency_days?: number | null
  anchor: 'completion' | 'schedule'
  statutory: boolean
  is_active: boolean
}

export interface ComplianceScheduleStats {
  total_active: number
  current: number
  due_soon: number
  overdue: number
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface CompleteRecordPayload {
  completed_at?: string
  check_passed?: boolean
  notes?: string
  evidence_asset_ids?: number[]
  due_date?: string
}

/**
 * Create payload, mirroring `RequirementCreate` in
 * `src/api/schemas/compliance_schedule.py`.
 *
 * `template_id` is deliberately absent. The schema accepts it as a
 * client-settable foreign key with no validation, so a wrong value surfaces as
 * an unhandled integrity error rather than a rejected field — not something a
 * form should be able to reach.
 */
export interface RequirementCreatePayload {
  title: string
  taxonomy_id: string
  next_due_date: string
  description?: string | null
  regulatory_basis?: string | null
  frequency_months?: number | null
  frequency_days?: number | null
  anchor?: 'completion' | 'schedule'
  statutory?: boolean
  location_id?: number | null
  owner_id?: number | null
}

/**
 * Update payload, mirroring `RequirementUpdate`. Every field is optional and the
 * route applies `exclude_unset`, so an absent key means "leave alone" while an
 * explicit `null` clears the value. Callers must therefore omit keys they do not
 * intend to change rather than sending undefined-ish placeholders.
 */
export type RequirementUpdatePayload = Partial<RequirementCreatePayload> & {
  is_active?: boolean
}

export function createComplianceScheduleApi(api: AxiosInstance) {
  // The shared axios instance sets baseURL to the host only, with no version
  // segment, so every client spells `/api/v1` itself. Omitting it here sent all
  // twelve of these requests to paths the server does not serve, and each one
  // answered 404 in every environment.
  const base = '/api/v1/compliance-schedule'

  return {
    listRequirements: (params?: {
      is_active?: boolean
      location_id?: number
      status?: ComplianceStatus
      page?: number
      page_size?: number
    }) => api.get<Paginated<ComplianceRequirement>>(`${base}/requirements`, { params }),

    getRequirement: (id: number) => api.get<ComplianceRequirement>(`${base}/requirements/${id}`),

    createRequirement: (data: RequirementCreatePayload) =>
      api.post<ComplianceRequirement>(`${base}/requirements`, data),

    updateRequirement: (id: number, data: RequirementUpdatePayload) =>
      api.patch<ComplianceRequirement>(`${base}/requirements/${id}`, data),

    deactivateRequirement: (id: number) =>
      api.post<ComplianceRequirement>(`${base}/requirements/${id}/deactivate`),

    listRecords: (requirementId: number, params?: { page?: number; page_size?: number }) =>
      api.get<Paginated<ComplianceRecord>>(`${base}/requirements/${requirementId}/records`, {
        params,
      }),

    completeRequirement: (requirementId: number, data: CompleteRecordPayload) =>
      api.post<ComplianceRecord>(`${base}/requirements/${requirementId}/records`, data),

    getRecord: (id: number) => api.get<ComplianceRecord>(`${base}/records/${id}`),

    attachEvidence: (recordId: number, evidence_asset_ids: number[]) =>
      api.post<ComplianceRecord>(`${base}/records/${recordId}/evidence`, { evidence_asset_ids }),

    listCatalogue: (active_only = true) =>
      api.get<{ items: CatalogueTemplate[]; total: number }>(`${base}/catalogue`, {
        params: { active_only },
      }),

    activateCatalogue: (
      templateKey: string,
      data?: {
        location_id?: number
        next_due_date?: string
        last_completed_at?: string
        owner_id?: number
      },
    ) => api.post<ComplianceRequirement>(`${base}/catalogue/${templateKey}/activate`, data ?? {}),

    getStats: () => api.get<ComplianceScheduleStats>(`${base}/stats`),
  }
}

export type ComplianceScheduleApi = ReturnType<typeof createComplianceScheduleApi>
