/**
 * Users / roles API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance, AxiosRequestConfig } from 'axios'

/** Minimal paginated shape used by users list responses. */
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

export interface UserSearchResult {
  id: number
  email: string
  full_name: string
  display_name?: string
  avatar_url?: string
  department?: string
}

export interface UserDetail {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  department?: string
  phone?: string
  job_title?: string
  is_active: boolean
  is_superuser: boolean
  last_login?: string
  azure_oid?: string | null
  tenant_id?: number | null
  created_at: string
  roles: RoleDetail[]
}

export interface RoleDetail {
  id: number
  name: string
  description?: string
  permissions?: string | null
  is_system_role: boolean
}

export interface UserCreatePayload {
  email: string
  auth_provider?: 'microsoft_sso' | 'local'
  password?: string
  first_name: string
  last_name: string
  department?: string
  phone?: string
  job_title?: string
  is_active?: boolean
  is_superuser?: boolean
  tenant_id?: number | null
  role_ids?: number[]
}

export interface UserUpdatePayload {
  email?: string
  first_name?: string
  last_name?: string
  department?: string
  phone?: string
  job_title?: string
  is_active?: boolean
  is_superuser?: boolean
  tenant_id?: number | null
  role_ids?: number[]
}

export interface RoleCreatePayload {
  name: string
  description?: string
  permissions: string[]
}

export interface RoleUpdatePayload {
  name?: string
  description?: string
  permissions?: string[]
}

export function createUsersApi(api: AxiosInstance) {
  return {
  search: (query: string) =>
    api.get<UserSearchResult[]>(`/api/v1/users/search/?q=${encodeURIComponent(query)}`),
  list: (
    page = 1,
    size = 50,
    params?: { search?: string; department?: string; is_active?: boolean },
    config?: AxiosRequestConfig,
  ) => {
    const sp = new URLSearchParams({
      page: String(page),
      page_size: String(size),
    })
    if (params?.search) sp.set('search', params.search)
    if (params?.department) sp.set('department', params.department)
    if (params?.is_active !== undefined) sp.set('is_active', String(params.is_active))
    return api.get<PaginatedResponse<UserDetail>>(`/api/v1/users/?${sp}`, config)
  },
  get: (id: number) => api.get<UserDetail>(`/api/v1/users/${id}`),
  create: (data: UserCreatePayload) => api.post<UserDetail>('/api/v1/users/', data),
  update: (id: number, data: UserUpdatePayload) =>
    api.patch<UserDetail>(`/api/v1/users/${id}`, data),
  delete: (id: number) => api.delete<void>(`/api/v1/users/${id}`),
  listRoles: (config?: AxiosRequestConfig) =>
    api.get<RoleDetail[]>('/api/v1/users/roles/', config),
  createRole: (data: RoleCreatePayload) => api.post<RoleDetail>('/api/v1/users/roles/', data),
  updateRole: (id: number, data: RoleUpdatePayload) =>
    api.patch<RoleDetail>(`/api/v1/users/roles/${id}`, data),
}
}
