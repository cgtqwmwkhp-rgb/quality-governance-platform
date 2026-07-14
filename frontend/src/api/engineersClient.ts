/**
 * Thin engineers API client for portal self-inbox (CUJ-P10).
 * Instantiated from `client.ts` with the shared axios instance.
 */
import type { AxiosInstance } from 'axios'

export interface EngineerSelfProfile {
  id: number
  external_id: string
  user_id: number
  employee_number?: string | null
  job_title?: string | null
  department?: string | null
  site?: string | null
  is_active: boolean
}

export function createEngineersApi(api: AxiosInstance) {
  return {
    /** Resolve linked engineer for the current user. 404 = not linked. */
    getByUserMe: () => api.get<EngineerSelfProfile>('/api/v1/engineers/by-user/me'),
  }
}
