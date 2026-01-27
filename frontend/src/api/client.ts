import axios, { AxiosError } from 'axios'
import { getPlatformToken, isTokenExpired, clearTokens } from '../utils/auth'

// HARDCODED HTTPS - bypassing any potential env var issues
const HTTPS_API_BASE = 'https://app-qgp-prod.azurewebsites.net';

// Request timeout in milliseconds (15 seconds)
// Prevents infinite spinner if backend hangs
const REQUEST_TIMEOUT_MS = 15000;

// ============ Bounded Error Codes (LOGIN_UX_CONTRACT.md) ============
// These are the ONLY allowed error codes for login
export type LoginErrorCode =
  | 'TIMEOUT'
  | 'UNAUTHORIZED'
  | 'UNAVAILABLE'
  | 'SERVER_ERROR'
  | 'NETWORK_ERROR'
  | 'UNKNOWN';

// Error code to user message mapping (bounded, no PII)
export const LOGIN_ERROR_MESSAGES: Record<LoginErrorCode, string> = {
  TIMEOUT: 'Request timed out. Please try again.',
  UNAUTHORIZED: 'Incorrect email or password.',
  UNAVAILABLE: 'Service temporarily unavailable. Please try again in a few minutes.',
  SERVER_ERROR: 'Something went wrong. Please try again.',
  NETWORK_ERROR: 'Unable to connect. Please check your internet connection.',
  UNKNOWN: 'An unexpected error occurred. Please try again.',
};

// Duration buckets for telemetry
export type DurationBucket = 'fast' | 'normal' | 'slow' | 'very_slow' | 'timeout';

export function getDurationBucket(durationMs: number): DurationBucket {
  if (durationMs < 1000) return 'fast';
  if (durationMs < 3000) return 'normal';
  if (durationMs < 7000) return 'slow';
  if (durationMs < 15000) return 'very_slow';
  return 'timeout';
}

/**
 * Classify an error into a bounded LoginErrorCode.
 * MUST return one of the defined codes - no exceptions.
 */
export function classifyLoginError(error: unknown): LoginErrorCode {
  if (!axios.isAxiosError(error)) {
    return 'UNKNOWN';
  }
  
  const axiosError = error as AxiosError;
  
  // Timeout check first (no response)
  if (axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout')) {
    return 'TIMEOUT';
  }
  
  // Network error (no response received)
  if (!axiosError.response) {
    return 'NETWORK_ERROR';
  }
  
  // HTTP status-based classification
  const status = axiosError.response.status;
  
  if (status === 401) {
    return 'UNAUTHORIZED';
  }
  
  if (status === 502 || status === 503) {
    return 'UNAVAILABLE';
  }
  
  if (status >= 500) {
    return 'SERVER_ERROR';
  }
  
  // Any other error
  return 'UNKNOWN';
}

const api = axios.create({
  baseURL: HTTPS_API_BASE,
  timeout: REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
})

// CRITICAL: Enforce HTTPS on all requests at interceptor level
api.interceptors.request.use((config) => {
  // Force HTTPS on baseURL
  if (config.baseURL && !config.baseURL.startsWith('https://')) {
    config.baseURL = config.baseURL.replace(/^http:/, 'https:');
    if (!config.baseURL.startsWith('https://')) {
      config.baseURL = 'https://' + config.baseURL.replace(/^\/\//, '');
    }
  }
  
  // Force HTTPS on URL if it's absolute
  if (config.url && config.url.startsWith('http:')) {
    config.url = config.url.replace(/^http:/, 'https:');
  }
  
  // Add auth token using centralized accessor
  const token = getPlatformToken()
  
  // DEBUG: Log auth header presence (not the token itself)
  const isApiCall = config.url?.startsWith('/api/')
  const isAuthEndpoint = config.url?.includes('/auth/login') || config.url?.includes('/auth/token-exchange')
  
  if (isApiCall && !isAuthEndpoint) {
    console.log(`[Auth Debug] ${config.method?.toUpperCase()} ${config.url} | token_present=${!!token} | token_length=${token?.length || 0}`)
  }
  
  if (token) {
    // Check if token is expired before attaching
    if (isTokenExpired(token)) {
      console.warn('[Axios] Token expired - clearing and redirecting to login')
      // Clear expired tokens
      clearTokens()
      // Only redirect if not already on login page and not an auth endpoint
      const currentPath = window.location.pathname
      const isLoginPage = currentPath === '/login' || currentPath === '/portal' || currentPath === '/portal/login'
      if (!isLoginPage && !isAuthEndpoint) {
        window.location.href = '/login'
        // Return a rejected promise to stop the request
        return Promise.reject(new Error('Token expired - redirecting to login'))
      }
    } else {
      config.headers.Authorization = `Bearer ${token}`
    }
  } else if (isApiCall && !isAuthEndpoint) {
    console.warn('[Auth Debug] No token available for API call - will likely get 401')
  }
  return config
})

// Handle error responses with proper classification
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Classify the error for better user messaging
    const status = error.response?.status
    const currentPath = window.location.pathname
    const isLoginPage = currentPath === '/login' || currentPath === '/portal' || currentPath === '/portal/login'
    
    if (status === 401) {
      // Token is invalid or expired
      const isAuthEndpoint = error.config?.url?.includes('/auth/')
      
      // Only auto-redirect for auth endpoint failures (login failures)
      if (isAuthEndpoint && !isLoginPage) {
        clearTokens()
        window.location.href = '/login'
      }
      // For data endpoints, enhance the error with a clear message
      if (!error.response?.data) {
        (error as any).classifiedMessage = 'Session expired. Please sign in again.'
      }
    } else if (status === 403) {
      (error as any).classifiedMessage = "You don't have permission to perform this action."
    } else if (status === 422) {
      // Validation error - message should come from server
      const data = error.response?.data as any
      (error as any).classifiedMessage = data?.detail || data?.message || 'Validation error. Please check your input.'
    } else if (status && status >= 500) {
      (error as any).classifiedMessage = 'Server error. Please try again later.'
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      // Request timed out
      (error as any).classifiedMessage = 'Request timed out. Please try again.'
      ;(error as any).isTimeout = true
    } else if (!error.response) {
      // No response - true network error or CORS issue
      (error as any).classifiedMessage = 'Network error. Please check your connection and try again.'
    }
    
    return Promise.reject(error)
  }
)

/**
 * Get a user-friendly error message from an API error.
 * Use this in catch blocks for consistent error messaging.
 */
export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    // Use classified message if available
    if ((error as any).classifiedMessage) {
      return (error as any).classifiedMessage
    }
    // Fall back to server-provided message
    const data = error.response?.data as any
    if (data?.message) {
      return data.message
    }
    if (data?.detail) {
      return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    }
    // Last resort - use axios error message
    return error.message
  }
  // Non-axios error
  if (error instanceof Error) {
    return error.message
  }
  return 'An unexpected error occurred'
}

// ============ Auth Types ============
export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

// ============ Common Types ============
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
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
  created_at: string
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
  reporter_email?: string
  reporter_name?: string
}

export interface IncidentUpdate {
  title?: string
  description?: string
  incident_type?: string
  severity?: string
  status?: string
  location?: string
  department?: string
}

// ============ RTA Types ============
export interface RTA {
  id: number
  reference_number: string
  title: string
  description: string
  severity: string
  status: string
  collision_date: string
  reported_date: string
  location: string
  road_name?: string
  postcode?: string
  weather_conditions?: string
  road_conditions?: string
  company_vehicle_registration?: string
  driver_name?: string
  driver_injured: boolean
  police_attended: boolean
  police_reference?: string
  insurance_notified: boolean
  created_at: string
}

export interface RTACreate {
  title: string
  description: string
  severity: string
  collision_date: string
  reported_date: string
  location: string
  road_name?: string
  postcode?: string
  weather_conditions?: string
  road_conditions?: string
  company_vehicle_registration?: string
  driver_name?: string
  driver_injured?: boolean
  police_attended?: boolean
}

export interface RTAUpdate {
  title?: string
  description?: string
  severity?: string
  status?: string
  location?: string
  company_vehicle_registration?: string
  driver_name?: string
  driver_injured?: boolean
  police_attended?: boolean
}

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
  resolution_summary?: string
  created_at: string
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
  resolution_summary?: string
}

// ============ Policy Types ============
export interface Policy {
  id: number
  reference_number: string
  title: string
  description?: string
  document_type: string
  status: string
  category?: string
  department?: string
  review_frequency_months: number
  next_review_date?: string
  is_public: boolean
  created_at: string
}

export interface PolicyCreate {
  title: string
  description?: string
  document_type: string
  category?: string
  department?: string
  review_frequency_months?: number
}

// ============ Risk Types ============
export interface Risk {
  id: number
  reference_number: string
  title: string
  description: string
  category: string
  subcategory?: string
  likelihood: number
  impact: number
  risk_score: number
  risk_level: string
  status: string
  department?: string
  treatment_strategy: string
  treatment_plan?: string
  next_review_date?: string
  is_active: boolean
  created_at: string
}

export interface RiskCreate {
  title: string
  description: string
  category: string
  subcategory?: string
  likelihood: number
  impact: number
  department?: string
  treatment_strategy?: string
  treatment_plan?: string
}

// ============ Audit Types ============
export interface AuditRun {
  id: number
  reference_number: string
  template_id: number
  title?: string
  location?: string
  status: 'draft' | 'scheduled' | 'in_progress' | 'pending_review' | 'completed' | 'cancelled'
  scheduled_date?: string
  due_date?: string
  started_at?: string
  completed_at?: string
  score?: number
  max_score?: number
  score_percentage?: number
  passed?: boolean
  created_at: string
}

export interface AuditFinding {
  id: number
  reference_number: string
  run_id: number
  title: string
  description: string
  severity: string
  finding_type: string
  status: 'open' | 'in_progress' | 'pending_verification' | 'closed' | 'deferred'
  corrective_action_required: boolean
  corrective_action_due_date?: string
  created_at: string
}

export interface AuditTemplate {
  id: number
  reference_number: string
  name: string
  description?: string
  category?: string
  audit_type: string
  is_active: boolean
  is_published: boolean
  created_at: string
}

export interface AuditRunCreate {
  template_id: number
  title?: string
  location?: string
  scheduled_date?: string
  due_date?: string
}

// ============ Investigation Types ============
export interface Investigation {
  id: number
  reference_number: string
  template_id: number
  assigned_entity_type: 'road_traffic_collision' | 'reporting_incident' | 'complaint'
  assigned_entity_id: number
  status: 'draft' | 'in_progress' | 'under_review' | 'completed' | 'closed'
  title: string
  description?: string
  data: Record<string, unknown>
  started_at?: string
  completed_at?: string
  created_at: string
}

export interface InvestigationCreate {
  template_id: number
  assigned_entity_type: string
  assigned_entity_id: number
  title: string
  description?: string
}

// === From-Record Types (Stage 2.1) ===
export interface CreateFromRecordRequest {
  source_type: 'near_miss' | 'road_traffic_collision' | 'complaint' | 'reporting_incident'
  source_id: number
  title: string
  template_id?: number
}

export interface CreateFromRecordError {
  error_code: 'VALIDATION_ERROR' | 'SOURCE_NOT_FOUND' | 'INV_ALREADY_EXISTS' | 'TEMPLATE_NOT_FOUND' | 'INTERNAL_ERROR'
  message: string
  details?: {
    existing_investigation_id?: number
    existing_reference_number?: string
    source_type?: string
    source_id?: number
  }
  request_id?: string
}

export interface SourceRecordItem {
  source_id: number
  display_label: string
  reference_number: string
  status: string
  created_at: string
  investigation_id: number | null
  investigation_reference: string | null
}

export interface SourceRecordsResponse {
  items: SourceRecordItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
  source_type: string
}

// ============ Standard Types ============
export interface Standard {
  id: number
  code: string
  name: string
  full_name: string
  version: string
  description?: string
  is_active: boolean
  created_at: string
}

export interface Clause {
  id: number
  standard_id: number
  clause_number: string
  title: string
  description?: string
  level: number
  is_active: boolean
}

export interface Control {
  id: number
  clause_id: number
  control_number: string
  title: string
  description?: string
  implementation_status?: string
  is_applicable: boolean
}

// ============ Action Types ============
export interface Action {
  id: number
  reference_number: string
  title: string
  description: string
  action_type: string
  priority: string
  status: 'open' | 'in_progress' | 'pending_verification' | 'completed' | 'cancelled'
  due_date?: string
  completed_at?: string
  source_type: string
  source_id: number
  created_at: string
}

export interface ActionCreate {
  title: string
  description: string
  action_type?: string
  priority?: string
  due_date?: string
  source_type: string
  source_id: number
  assigned_to_email?: string
}

// ============ API Functions ============
export const authApi = {
  login: (data: LoginRequest) => 
    api.post<LoginResponse>('/api/v1/auth/login', data),
}

// NOTE: All list endpoints use trailing slash (e.g., /incidents/) because
// FastAPI routes are defined with trailing slashes and redirect_slashes is disabled

export const incidentsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Incident>>(`/api/v1/incidents/?page=${page}&size=${size}`),
  create: (data: IncidentCreate) => 
    api.post<Incident>('/api/v1/incidents/', data),
  get: (id: number) => 
    api.get<Incident>(`/api/v1/incidents/${id}`),
  update: (id: number, data: IncidentUpdate) =>
    api.patch<Incident>(`/api/v1/incidents/${id}`, data),
}

export const rtasApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<RTA>>(`/api/v1/rtas/?page=${page}&size=${size}`),
  create: (data: RTACreate) => 
    api.post<RTA>('/api/v1/rtas/', data),
  get: (id: number) => 
    api.get<RTA>(`/api/v1/rtas/${id}`),
  update: (id: number, data: RTAUpdate) =>
    api.patch<RTA>(`/api/v1/rtas/${id}`, data),
}

export const complaintsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Complaint>>(`/api/v1/complaints/?page=${page}&size=${size}`),
  create: (data: ComplaintCreate) => 
    api.post<Complaint>('/api/v1/complaints/', data),
  get: (id: number) => 
    api.get<Complaint>(`/api/v1/complaints/${id}`),
  update: (id: number, data: ComplaintUpdate) =>
    api.patch<Complaint>(`/api/v1/complaints/${id}`, data),
}

export const policiesApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Policy>>(`/api/v1/policies/?page=${page}&size=${size}`),
  create: (data: PolicyCreate) => 
    api.post<Policy>('/api/v1/policies/', data),
  get: (id: number) => 
    api.get<Policy>(`/api/v1/policies/${id}`),
}

export const risksApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Risk>>(`/api/v1/risks/?page=${page}&size=${size}`),
  create: (data: RiskCreate) => 
    api.post<Risk>('/api/v1/risks/', data),
  get: (id: number) => 
    api.get<Risk>(`/api/v1/risks/${id}`),
}

export const auditsApi = {
  listRuns: (page = 1, size = 10) => 
    api.get<PaginatedResponse<AuditRun>>(`/api/v1/audits/runs/?page=${page}&size=${size}`),
  listTemplates: (page = 1, size = 10) => 
    api.get<PaginatedResponse<AuditTemplate>>(`/api/v1/audits/templates/?page=${page}&size=${size}`),
  listFindings: (page = 1, size = 10) => 
    api.get<PaginatedResponse<AuditFinding>>(`/api/v1/audits/findings/?page=${page}&size=${size}`),
  createRun: (data: AuditRunCreate) => 
    api.post<AuditRun>('/api/v1/audits/runs/', data),
  getRun: (id: number) => 
    api.get<AuditRun>(`/api/v1/audits/runs/${id}`),
}

/**
 * Investigation update payload - all fields optional for partial updates.
 */
export interface InvestigationUpdate {
  title?: string
  status?: string
  data?: Record<string, unknown>
  notes?: string
}

/**
 * Autosave payload with version for optimistic locking.
 */
export interface InvestigationAutosave {
  data: Record<string, unknown>
  version: number
}

export const investigationsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Investigation>>(`/api/v1/investigations/?page=${page}&size=${size}`),
  create: (data: InvestigationCreate) => 
    api.post<Investigation>('/api/v1/investigations/', data),
  get: (id: number) => 
    api.get<Investigation>(`/api/v1/investigations/${id}`),
  /**
   * Update investigation with partial data.
   * Returns updated investigation on success.
   */
  update: (id: number, data: InvestigationUpdate) =>
    api.patch<Investigation>(`/api/v1/investigations/${id}`, data),
  /**
   * Autosave investigation with version-based optimistic locking.
   * Returns 409 CONFLICT if version mismatch (stale data).
   */
  autosave: (id: number, data: InvestigationAutosave) =>
    api.patch<Investigation>(`/api/v1/investigations/${id}/autosave`, data),
  /**
   * Create investigation from source record using proper JSON body.
   * Returns 201 on success, 404 if source not found, 409 if already investigated.
   */
  createFromRecord: (data: CreateFromRecordRequest) =>
    api.post<Investigation>('/api/v1/investigations/from-record', data),
  /**
   * List source records available for investigation creation.
   * Records with investigation_id !== null are already investigated.
   */
  listSourceRecords: (
    source_type: string,
    options?: { q?: string; page?: number; size?: number }
  ) => {
    const params = new URLSearchParams({ source_type })
    if (options?.q) params.set('q', options.q)
    if (options?.page) params.set('page', String(options.page))
    if (options?.size) params.set('size', String(options.size))
    return api.get<SourceRecordsResponse>(`/api/v1/investigations/source-records?${params}`)
  },
}

export const standardsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Standard>>(`/api/v1/standards/?page=${page}&page_size=${size}`),
  get: (id: number) => 
    api.get<Standard & { clauses: Clause[] }>(`/api/v1/standards/${id}`),
  getClauses: (standardId: number) => 
    api.get<Clause[]>(`/api/v1/standards/${standardId}/clauses/`),
  getControls: (clauseId: number) => 
    api.get<Control[]>(`/api/v1/clauses/${clauseId}/controls/`),
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

export const actionsApi = {
  /**
   * List all actions with pagination and optional filters.
   * Actions are returned sorted by created_at descending for stable ordering.
   */
  list: (page = 1, size = 10, status?: string, source_type?: string) => 
    api.get<PaginatedResponse<Action>>(`/api/v1/actions/?page=${page}&size=${size}${status ? `&status=${status}` : ''}${source_type ? `&source_type=${source_type}` : ''}`),
  /**
   * Create a new action linked to a source entity.
   */
  create: (data: ActionCreate) => 
    api.post<Action>('/api/v1/actions/', data),
  /**
   * Get a single action by ID. Requires source_type.
   */
  get: (id: number, source_type: string) => 
    api.get<Action>(`/api/v1/actions/${id}?source_type=${source_type}`),
  /**
   * Update an action with partial data. Requires source_type.
   * Returns 404 if not found, 400 for validation errors.
   */
  update: (id: number, source_type: string, data: ActionUpdate) => 
    api.patch<Action>(`/api/v1/actions/${id}?source_type=${source_type}`, data),
}

// User type for search results
export interface UserSearchResult {
  id: number
  email: string
  full_name: string
  department?: string
}

export const usersApi = {
  search: (query: string) =>
    api.get<UserSearchResult[]>(`/api/v1/users/search/?q=${encodeURIComponent(query)}`),
  list: (page = 1, size = 50) =>
    api.get<PaginatedResponse<UserSearchResult>>(`/api/v1/users/?page=${page}&size=${size}`),
}

export default api
