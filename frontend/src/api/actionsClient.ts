/**
 * Actions API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

/** Minimal paginated shape used by action list responses. */
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

// ============ Action Types ============
export interface Action {
  id: number
  reference_number?: string
  title: string
  description: string
  action_type: string
  priority: string
  status:
    | 'open'
    | 'in_progress'
    | 'pending_verification'
    | 'completed'
    | 'cancelled'
    | 'closed'
    | 'verified'
    | 'overdue'
    | 'verification'
  /** Normalized for KPIs (e.g. CAPA closed → completed) */
  display_status: string
  /** Stable id: capa:12, incident_action:3 */
  action_key: string
  due_date?: string
  completed_at?: string
  completion_notes?: string
  source_type: string
  source_id: number
  source_reference?: string
  source_title?: string
  source_scheme?: string
  clause_reference?: string
  /** Present when source_type is audit_finding — parent run for navigation */
  audit_run_id?: number | null
  owner_id?: number
  owner_email?: string
  assigned_to_email?: string
  created_at: string
}

export interface ActionsSummary {
  total: number
  by_display_status: Record<string, number>
}

export interface ActionCreate {
  title: string
  description: string
  action_type?: string
  priority?: string
  due_date?: string
  source_type: string
  source_id?: number
  source_reference?: string
  assigned_to_email?: string
}

/**
 * Action update payload - all fields optional for partial updates.
 */
export interface ActionUpdate {
  title?: string
  description?: string
  action_type?: string
  priority?: string
  status?: string
  due_date?: string
  assigned_to_email?: string
  completion_notes?: string
}

/** Time-stamped owner commentary on a unified action (from GET/POST .../by-key/notes). */
export interface ActionOwnerNote {
  id: number
  action_key: string
  body: string
  author_id: number
  author_email?: string
  created_at: string
}

export interface ActionOwnerNoteListResponse {
  items: ActionOwnerNote[]
}

export function createActionsApi(api: AxiosInstance) {
  return {
  /**
   * List all actions with pagination and optional filters.
   * Actions are returned sorted by created_at descending for stable ordering.
   */
  list: (page = 1, pageSize = 10, status?: string, source_type?: string, source_id?: number) =>
    api.get<PaginatedResponse<Action>>(
      `/api/v1/actions/?page=${page}&page_size=${pageSize}${status ? `&status=${status}` : ''}${source_type ? `&source_type=${source_type}` : ''}${source_id ? `&source_id=${source_id}` : ''}`,
    ),
  /** Tenant-wide totals by display_status (not limited to first page). */
  summary: () => api.get<ActionsSummary>('/api/v1/actions/summary'),
  /**
   * Create a new action linked to a source entity.
   */
  create: (data: ActionCreate) => api.post<Action>('/api/v1/actions/', data),
  /**
   * Get a single action by ID. Requires source_type.
   */
  get: (id: number, source_type: string) =>
    api.get<Action>(`/api/v1/actions/${id}?source_type=${encodeURIComponent(source_type)}`),
  /** Resolve by stable action_key from list responses. */
  getByKey: (key: string) =>
    api.get<Action>(`/api/v1/actions/by-key?key=${encodeURIComponent(key)}`),
  /**
   * Update an action with partial data. Requires source_type.
   * Returns 404 if not found, 400 for validation errors.
   */
  update: (id: number, source_type: string, data: ActionUpdate) =>
    api.patch<Action>(
      `/api/v1/actions/${id}?source_type=${encodeURIComponent(source_type)}`,
      data,
    ),
  /** Owner commentary for an action; newest first. */
  listOwnerNotes: (actionKey: string, limit = 100) =>
    api.get<ActionOwnerNoteListResponse>(
      `/api/v1/actions/by-key/notes?key=${encodeURIComponent(actionKey)}&limit=${limit}`,
    ),
  appendOwnerNote: (actionKey: string, body: string) =>
    api.post<ActionOwnerNote>('/api/v1/actions/by-key/notes', { key: actionKey, body }),
}
}
