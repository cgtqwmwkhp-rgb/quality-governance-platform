/**
 * Signatures API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

export interface SignatureRequestEntry {
  id: number
  reference_number: string
  title: string
  description?: string
  document_type: string
  workflow_type: string
  status: string
  expires_at?: string
  created_at: string
  completed_at?: string
  signers: {
    id: number
    email: string
    name: string
    role: string
    order: number
    status: string
    signed_at?: string
    declined_at?: string
  }[]
}

export function createSignaturesApi(api: AxiosInstance) {
  return {
    list: (status?: string, limit = 50) => {
      const sp = new URLSearchParams({ limit: String(limit) })
      if (status) sp.set('status', status)
      return api.get<SignatureRequestEntry[]>(`/api/v1/signatures/requests?${sp}`)
    },
    get: (id: number) => api.get<SignatureRequestEntry>(`/api/v1/signatures/requests/${id}`),
    create: (data: {
      title: string
      description?: string
      document_type: string
      document_id?: string
      workflow_type?: string
      require_all?: boolean
      expires_in_days?: number
      signers: { email: string; name: string; role?: string; order?: number }[]
    }) => api.post<SignatureRequestEntry>('/api/v1/signatures/requests', data),
    send: (id: number) =>
      api.post<{ status: string; reference: string }>(`/api/v1/signatures/requests/${id}/send`),
    void: (id: number, reason?: string) =>
      api.post<{ status: string; reference: string }>(`/api/v1/signatures/requests/${id}/void`, {
        reason,
      }),
    getPending: () => api.get<SignatureRequestEntry[]>('/api/v1/signatures/requests/pending'),
    getAuditLog: (id: number) => api.get<unknown[]>(`/api/v1/signatures/requests/${id}/audit-log`),
    getStats: () =>
      api.get<{
        requests_by_status: Record<string, number>
        total_signatures: number
        requests_this_month: number
      }>('/api/v1/signatures/stats'),
    listTemplates: () => api.get<unknown[]>('/api/v1/signatures/templates'),
    createTemplate: (data: {
      name: string
      description?: string
      signer_roles?: unknown[]
      workflow_type?: string
    }) => api.post<unknown>('/api/v1/signatures/templates', data),
  }
}
