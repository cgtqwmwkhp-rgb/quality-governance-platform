/**
 * Audit Trail API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

export interface AuditLogEntry {
  id: number
  sequence: number
  entry_hash: string
  entity_type: string
  entity_id: string
  entity_name?: string
  action: string
  action_category: string
  user_id?: number
  user_email?: string
  user_name?: string
  changed_fields?: string[]
  ip_address?: string
  timestamp: string
  is_sensitive: boolean
  old_values?: Record<string, unknown>
  new_values?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface AuditVerification {
  id: number
  start_sequence: number
  end_sequence: number
  is_valid: boolean
  entries_verified: number
  invalid_entries?: unknown[]
  verified_at: string
}

export function createAuditTrailApi(api: AxiosInstance) {
  const silent = { suppressErrorToast: true } as const
  return {
    list: (params?: {
      entity_type?: string
      action?: string
      user_id?: number
      date_from?: string
      date_to?: string
      page?: number
      per_page?: number
    }) => {
      const sp = new URLSearchParams()
      if (params?.entity_type) sp.set('entity_type', params.entity_type)
      if (params?.action) sp.set('action', params.action)
      if (params?.user_id) sp.set('user_id', String(params.user_id))
      if (params?.date_from) sp.set('date_from', params.date_from)
      if (params?.date_to) sp.set('date_to', params.date_to)
      sp.set('page', String(params?.page || 1))
      sp.set('per_page', String(params?.per_page || 50))
      return api.get<{
        items: AuditLogEntry[]
        total: number
        page: number
        per_page: number
      }>(`/api/v1/audit-trail/?${sp}`, silent)
    },
    getEntry: (id: number) => api.get<AuditLogEntry>(`/api/v1/audit-trail/${id}`),
    getByEntity: (entityType: string, entityId: string) =>
      api.get<AuditLogEntry[]>(`/api/v1/audit-trail/entity/${entityType}/${entityId}`),
    getByUser: (userId: number, days = 30) =>
      api.get<AuditLogEntry[]>(`/api/v1/audit-trail/user/${userId}?days=${days}`),
    verify: () => api.post<AuditVerification>('/api/v1/audit-trail/verify'),
    exportLog: (params: {
      format?: string
      date_from?: string
      date_to?: string
      entity_type?: string
      reason?: string
    }) =>
      api.post<{
        export_id: number
        entries_count: number
        file_hash: string
        data?: unknown[]
      }>('/api/v1/audit-trail/export', params),
    getStats: (days = 30) =>
      api.get<Record<string, unknown>>(`/api/v1/audit-trail/stats?days=${days}`),
  }
}
