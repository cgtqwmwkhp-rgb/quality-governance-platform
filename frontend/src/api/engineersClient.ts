/**
 * Thin engineers API client for portal self-inbox (CUJ-P10).
 * Instantiated from `client.ts` with the shared axios instance.
 */
import type { AxiosInstance } from 'axios'

export interface EngineerSelfProfile {
  linked: boolean
  id?: number | null
  external_id?: string | null
  user_id?: number | null
  employee_number?: string | null
  job_title?: string | null
  department?: string | null
  site?: string | null
  is_active?: boolean | null
}

export function createEngineersApi(api: AxiosInstance) {
  return {
    /** Resolve linked engineer for the current user. linked=false = not linked (HTTP 200). */
    getByUserMe: () => api.get<EngineerSelfProfile>('/api/v1/engineers/by-user/me'),
  }
}
