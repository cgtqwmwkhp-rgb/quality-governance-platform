/**
 * Lookups API client extracted from `client.ts` (Preferred S7 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 * Returns unwrapped data (not AxiosResponse) for admin-config consumers.
 */
import type { AxiosInstance } from 'axios'

export interface LookupOption {
  id: number
  category: string
  code: string
  label: string
  description?: string
  is_active: boolean
  display_order: number
}

export function createLookupsApi(api: AxiosInstance) {
  return {
    list: (category: string, activeOnly = true) =>
      api
        .get<{
          items: LookupOption[]
          total: number
        }>(
          `/api/v1/admin/config/lookup/${category}${activeOnly ? '?is_active=true' : ''}`,
        )
        .then((r) => r.data),

    create: (category: string, data: Partial<LookupOption>) =>
      api
        .post<LookupOption>(`/api/v1/admin/config/lookup/${category}`, {
          ...data,
          // Path is authoritative; always include so older BE schemas still accept Admin create.
          category,
        })
        .then((r) => r.data),

    update: (category: string, id: number, data: Partial<LookupOption>) =>
      api
        .patch<LookupOption>(`/api/v1/admin/config/lookup/${category}/${id}`, data)
        .then((r) => r.data),

    delete: (category: string, id: number) =>
      api.delete<void>(`/api/v1/admin/config/lookup/${category}/${id}`).then((r) => r.data),
  }
}
