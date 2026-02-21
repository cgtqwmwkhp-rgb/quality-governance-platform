import axios, { AxiosError } from 'axios'
import { getPlatformToken, isTokenExpired, clearTokens } from '../utils/auth'
import { API_BASE_URL } from '../config/apiBase'
import { useAppStore } from '../stores/useAppStore'

// Use centralized API base URL from config (environment-aware)
const HTTPS_API_BASE = API_BASE_URL;

// Request timeout in milliseconds (15 seconds for normal requests)
// Prevents infinite spinner if backend hangs
const REQUEST_TIMEOUT_MS = 15000;

// Extended timeout for file uploads (2 minutes)
// File uploads to Azure Blob Storage can take longer, especially for large files
const UPLOAD_TIMEOUT_MS = 120000;

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

// ============ Bounded Error Classes for API Responses ============
// Universal error classification for all API calls

export enum ErrorClass {
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  AUTH_ERROR = 'AUTH_ERROR',
  NOT_FOUND = 'NOT_FOUND',
  NETWORK_ERROR = 'NETWORK_ERROR',
  SERVER_ERROR = 'SERVER_ERROR',
  SETUP_REQUIRED = 'SETUP_REQUIRED',
  UNKNOWN = 'UNKNOWN',
}

// Re-export SetupRequired types for convenience
export { isSetupRequired, SetupRequiredPanel } from '../components/ui/SetupRequiredPanel'
export type { SetupRequiredResponse } from '../components/ui/SetupRequiredPanel'

export interface ApiError extends Error {
  error_class: ErrorClass
  status_code?: number
  detail?: string
}

/**
 * Classify any error into a bounded ErrorClass.
 * Used for deterministic UX states.
 */
export function classifyError(error: unknown): ErrorClass {
  if (!axios.isAxiosError(error)) {
    return ErrorClass.UNKNOWN
  }

  const axiosError = error as AxiosError

  // Network error (no response)
  if (!axiosError.response) {
    if (axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout')) {
      return ErrorClass.NETWORK_ERROR
    }
    return ErrorClass.NETWORK_ERROR
  }

  const status = axiosError.response.status

  if (status === 400 || status === 422) {
    return ErrorClass.VALIDATION_ERROR
  }
  if (status === 401 || status === 403) {
    return ErrorClass.AUTH_ERROR
  }
  if (status === 404) {
    return ErrorClass.NOT_FOUND
  }
  if (status >= 500) {
    return ErrorClass.SERVER_ERROR
  }

  return ErrorClass.UNKNOWN
}

/**
 * Create a typed ApiError from any caught error.
 */
export function createApiError(error: unknown): ApiError {
  const errorClass = classifyError(error)
  const apiError = new Error('API Error') as ApiError
  apiError.error_class = errorClass

  if (axios.isAxiosError(error) && error.response) {
    apiError.status_code = error.response.status
    apiError.detail = error.response.data?.detail || error.response.data?.message || error.message
  }

  return apiError
}

const api = axios.create({
  baseURL: HTTPS_API_BASE,
  timeout: REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
})

let activeRequests = 0;

// CRITICAL: Enforce HTTPS on all requests at interceptor level
api.interceptors.request.use((config) => {
  activeRequests++;
  useAppStore.getState().setLoading(true);
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

interface ClassifiedAxiosError extends AxiosError {
  classifiedMessage?: string
  isTimeout?: boolean
}

api.interceptors.response.use(
  (response) => {
    activeRequests--;
    if (activeRequests === 0) {
      useAppStore.getState().setLoading(false);
    }
    useAppStore.getState().setConnectionStatus('connected');
    return response;
  },
  (error: AxiosError) => {
    activeRequests--;
    if (activeRequests === 0) {
      useAppStore.getState().setLoading(false);
    }
    if (!error.response) {
      useAppStore.getState().setConnectionStatus('disconnected');
    }
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
        (error as ClassifiedAxiosError).classifiedMessage = 'Session expired. Please sign in again.'
      }
    } else if (status === 403) {
      (error as ClassifiedAxiosError).classifiedMessage = "You don't have permission to perform this action."
    } else if (status === 422) {
      const data = error.response?.data as Record<string, unknown> | undefined
      (error as ClassifiedAxiosError).classifiedMessage = (data?.detail as string) || (data?.message as string) || 'Validation error. Please check your input.'
    } else if (status && status >= 500) {
      (error as ClassifiedAxiosError).classifiedMessage = 'Server error. Please try again later.'
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      (error as ClassifiedAxiosError).classifiedMessage = 'Request timed out. Please try again.'
      ;(error as ClassifiedAxiosError).isTimeout = true
    } else if (!error.response) {
      (error as ClassifiedAxiosError).classifiedMessage = 'Network error. Please check your connection and try again.'
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
    const classified = error as ClassifiedAxiosError
    if (classified.classifiedMessage) {
      return classified.classifiedMessage
    }
    const data = error.response?.data as Record<string, unknown> | undefined
    if (data?.message) {
      return data.message as string
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
  frequency?: string
  version: number
  scoring_method: string
  passing_score?: number
  allow_offline: boolean
  require_gps: boolean
  require_signature: boolean
  require_approval: boolean
  auto_create_findings: boolean
  is_active: boolean
  is_published: boolean
  archived_at?: string | null
  archived_by_id?: number | null
  created_by_id?: number
  created_at: string
  updated_at: string
}

export interface AuditTemplateCreate {
  name: string
  description?: string
  category?: string
  audit_type?: string
  frequency?: string
  scoring_method?: string
  passing_score?: number
  allow_offline?: boolean
  require_gps?: boolean
  require_signature?: boolean
  require_approval?: boolean
  auto_create_findings?: boolean
}

export interface AuditTemplateUpdate {
  name?: string
  description?: string
  category?: string
  audit_type?: string
  frequency?: string
  scoring_method?: string
  passing_score?: number
  allow_offline?: boolean
  require_gps?: boolean
  require_signature?: boolean
  require_approval?: boolean
  auto_create_findings?: boolean
}

export interface AuditRunCreate {
  template_id: number
  title?: string
  location?: string
  scheduled_date?: string
  due_date?: string
}

export interface AuditRunUpdate {
  title?: string
  location?: string
  status?: 'draft' | 'scheduled' | 'in_progress' | 'pending_review' | 'completed' | 'cancelled'
  scheduled_date?: string
  due_date?: string
  assigned_to_id?: number
}

export interface AuditTemplateDetail {
  id: number
  reference_number?: string
  name: string
  description?: string
  category?: string
  audit_type: string
  frequency?: string
  version: number
  scoring_method: string
  passing_score?: number
  allow_offline: boolean
  require_gps: boolean
  require_signature: boolean
  require_approval: boolean
  auto_create_findings: boolean
  is_published: boolean
  is_active: boolean
  created_by_id?: number
  sections: AuditSection[]
  section_count: number
  question_count: number
  created_at: string
  updated_at: string
}

export interface AuditSectionCreate {
  title: string
  description?: string
  sort_order?: number
  weight?: number
}

export interface AuditSectionUpdate {
  title?: string
  description?: string
  sort_order?: number
  weight?: number
}

export interface QuestionOptionBase {
  value: string
  label: string
  score?: number
  is_correct?: boolean
  triggers_finding?: boolean
}

export interface AuditQuestionCreate {
  section_id?: number
  question_text: string
  question_type: string
  description?: string
  help_text?: string
  is_required?: boolean
  allow_na?: boolean
  max_score?: number
  weight?: number
  options?: QuestionOptionBase[]
  sort_order?: number
  risk_category?: string
  risk_weight?: number
}

export interface AuditQuestionUpdate {
  question_text?: string
  question_type?: string
  description?: string
  help_text?: string
  is_required?: boolean
  allow_na?: boolean
  max_score?: number
  weight?: number
  options?: QuestionOptionBase[]
  min_value?: number | null
  max_value?: number | null
  decimal_places?: number | null
  min_length?: number | null
  max_length?: number | null
  sort_order?: number
  risk_category?: string
  risk_weight?: number
  is_active?: boolean
}

export interface AuditSection {
  id: number
  template_id: number
  title: string
  description?: string
  sort_order: number
  weight: number
  is_repeatable: boolean
  max_repeats?: number
  is_active: boolean
  questions: AuditQuestion[]
  created_at: string
  updated_at: string
}

export interface AuditQuestion {
  id: number
  template_id: number
  section_id?: number
  question_text: string
  question_type: string
  description?: string
  help_text?: string
  is_required: boolean
  allow_na: boolean
  is_active: boolean
  max_score?: number
  weight: number
  options?: QuestionOptionBase[]
  min_value?: number
  max_value?: number
  decimal_places?: number
  min_length?: number
  max_length?: number
  sort_order: number
  risk_category?: string
  risk_weight?: number
  created_at: string
  updated_at: string
}

export interface AuditResponse {
  id: number
  run_id: number
  question_id: number
  response_value?: string
  score?: number
  max_score?: number
  notes?: string
  created_at: string
}

export interface AuditResponseCreate {
  question_id: number
  response_value?: string
  score?: number
  max_score?: number
  notes?: string
}

export interface AuditResponseUpdate {
  response_value?: string
  score?: number
  notes?: string
}

export interface AuditFindingCreate {
  title: string
  description?: string
  severity: 'critical' | 'major' | 'minor' | 'observation'
  question_id?: number
  clause_ids?: number[]
  control_ids?: number[]
  risk_ids?: number[]
  recommended_action?: string
  due_date?: string
}

export interface AuditFindingUpdate {
  title?: string
  description?: string
  severity?: 'critical' | 'major' | 'minor' | 'observation'
  status?: 'open' | 'in_progress' | 'resolved' | 'verified' | 'closed'
  recommended_action?: string
  corrective_action?: string
  verified_by_id?: number
  verified_at?: string
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
  parent_clause_id?: number | null
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

export interface ControlListItem {
  id: number
  clause_id: number
  clause_number: string
  control_number: string
  title: string
  implementation_status?: string
  is_applicable: boolean
  is_active: boolean
}

export interface ComplianceScore {
  standard_id: number
  standard_code: string
  total_controls: number
  implemented_count: number
  partial_count: number
  not_implemented_count: number
  compliance_percentage: number
  setup_required: boolean
}

// ============ Action Types ============
export interface Action {
  id: number
  reference_number?: string
  title: string
  description: string
  action_type: string
  priority: string
  status: 'open' | 'in_progress' | 'pending_verification' | 'completed' | 'cancelled' | 'closed'
  due_date?: string
  completed_at?: string
  completion_notes?: string
  source_type: string
  source_id: number
  owner_id?: number
  owner_email?: string
  assigned_to_email?: string
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
    api.post<Incident>('/api/v1/incidents', data),
  get: (id: number) => 
    api.get<Incident>(`/api/v1/incidents/${id}`),
  update: (id: number, data: IncidentUpdate) =>
    api.patch<Incident>(`/api/v1/incidents/${id}`, data),
}

export const rtasApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<RTA>>(`/api/v1/rtas/?page=${page}&size=${size}`),
  create: (data: RTACreate) => 
    api.post<RTA>('/api/v1/rtas', data),
  get: (id: number) => 
    api.get<RTA>(`/api/v1/rtas/${id}`),
  update: (id: number, data: RTAUpdate) =>
    api.patch<RTA>(`/api/v1/rtas/${id}`, data),
}

export const complaintsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Complaint>>(`/api/v1/complaints/?page=${page}&size=${size}`),
  create: (data: ComplaintCreate) => 
    api.post<Complaint>('/api/v1/complaints', data),
  get: (id: number) => 
    api.get<Complaint>(`/api/v1/complaints/${id}`),
  update: (id: number, data: ComplaintUpdate) =>
    api.patch<Complaint>(`/api/v1/complaints/${id}`, data),
}

export const policiesApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Policy>>(`/api/v1/policies/?page=${page}&size=${size}`),
  create: (data: PolicyCreate) => 
    api.post<Policy>('/api/v1/policies', data),
  get: (id: number) => 
    api.get<Policy>(`/api/v1/policies/${id}`),
}

export const risksApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Risk>>(`/api/v1/risks/?page=${page}&size=${size}`),
  create: (data: RiskCreate) => 
    api.post<Risk>('/api/v1/risks', data),
  get: (id: number) => 
    api.get<Risk>(`/api/v1/risks/${id}`),
}

export const auditsApi = {
  // Templates - Full CRUD
  listTemplates: (page = 1, size = 20, params?: { search?: string; category?: string; is_published?: boolean }) => {
    const searchParams = new URLSearchParams({ page: String(page), page_size: String(size) })
    if (params?.search) searchParams.set('search', params.search)
    if (params?.category) searchParams.set('category', params.category)
    if (params?.is_published !== undefined) searchParams.set('is_published', String(params.is_published))
    return api.get<PaginatedResponse<AuditTemplate>>(`/api/v1/audits/templates?${searchParams}`)
  },
  getTemplate: (id: number) =>
    api.get<AuditTemplateDetail>(`/api/v1/audits/templates/${id}`),
  createTemplate: (data: AuditTemplateCreate) =>
    api.post<AuditTemplate>('/api/v1/audits/templates', data),
  updateTemplate: (id: number, data: AuditTemplateUpdate) =>
    api.patch<AuditTemplate>(`/api/v1/audits/templates/${id}`, data),
  publishTemplate: (id: number) =>
    api.post<AuditTemplate>(`/api/v1/audits/templates/${id}/publish`),
  cloneTemplate: (id: number) =>
    api.post<AuditTemplate>(`/api/v1/audits/templates/${id}/clone`),
  deleteTemplate: (id: number) =>
    api.delete(`/api/v1/audits/templates/${id}`),
  listArchivedTemplates: (page = 1, size = 20) =>
    api.get<PaginatedResponse<AuditTemplate>>(`/api/v1/audits/templates/archived?page=${page}&page_size=${size}`),
  restoreTemplate: (id: number) =>
    api.post<AuditTemplate>(`/api/v1/audits/templates/${id}/restore`),

  // Sections
  createSection: (templateId: number, data: AuditSectionCreate) =>
    api.post<AuditSection>(`/api/v1/audits/templates/${templateId}/sections`, data),
  updateSection: (sectionId: number, data: AuditSectionUpdate) =>
    api.patch<AuditSection>(`/api/v1/audits/sections/${sectionId}`, data),
  deleteSection: (sectionId: number) =>
    api.delete(`/api/v1/audits/sections/${sectionId}`),

  // Questions
  createQuestion: (templateId: number, data: AuditQuestionCreate) =>
    api.post<AuditQuestion>(`/api/v1/audits/templates/${templateId}/questions`, data),
  updateQuestion: (questionId: number, data: AuditQuestionUpdate) =>
    api.patch<AuditQuestion>(`/api/v1/audits/questions/${questionId}`, data),
  deleteQuestion: (questionId: number) =>
    api.delete(`/api/v1/audits/questions/${questionId}`),

  // Runs
  listRuns: (page = 1, size = 10) =>
    api.get<PaginatedResponse<AuditRun>>(`/api/v1/audits/runs?page=${page}&size=${size}`),
  createRun: (data: AuditRunCreate) =>
    api.post<AuditRun>('/api/v1/audits/runs', data),
  getRun: (id: number) =>
    api.get<AuditRun>(`/api/v1/audits/runs/${id}`),
  updateRun: (id: number, data: AuditRunUpdate) =>
    api.patch<AuditRun>(`/api/v1/audits/runs/${id}`, data),
  startRun: (id: number) =>
    api.post<AuditRun>(`/api/v1/audits/runs/${id}/start`),
  completeRun: (id: number) =>
    api.post<AuditRun>(`/api/v1/audits/runs/${id}/complete`),

  // Responses
  createResponse: (runId: number, data: AuditResponseCreate) =>
    api.post<AuditResponse>(`/api/v1/audits/runs/${runId}/responses`, data),
  updateResponse: (responseId: number, data: AuditResponseUpdate) =>
    api.patch<AuditResponse>(`/api/v1/audits/responses/${responseId}`, data),

  // Findings
  listFindings: (page = 1, size = 10, runId?: number) =>
    api.get<PaginatedResponse<AuditFinding>>(
      `/api/v1/audits/findings/?page=${page}&size=${size}${runId ? `&run_id=${runId}` : ''}`
    ),
  createFinding: (runId: number, data: AuditFindingCreate) =>
    api.post<AuditFinding>(`/api/v1/audits/runs/${runId}/findings`, data),
  updateFinding: (findingId: number, data: AuditFindingUpdate) =>
    api.patch<AuditFinding>(`/api/v1/audits/findings/${findingId}`, data),
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

// ============ Investigation Stage 1 API Types ============

export interface TimelineEvent {
  id: number
  created_at: string
  event_type: string
  field_path?: string
  old_value?: string
  new_value?: string
  actor_id?: number
  event_metadata?: Record<string, unknown>
}

export interface TimelineResponse {
  items: TimelineEvent[]
  total: number
  page: number
  page_size: number
  investigation_id: number
}

export interface InvestigationComment {
  id: number
  created_at: string
  author_id: number
  content: string  // Note content (backend field name)
  section_id?: string
  field_id?: string
  parent_comment_id?: number
}

export interface CommentsResponse {
  items: InvestigationComment[]
  total: number
  page: number
  page_size: number
  investigation_id: number
}

export interface CustomerPackSummary {
  id: number
  created_at: string
  pack_uuid: string
  audience: string
  checksum_sha256?: string
  generated_by_id?: number
}

export interface PacksResponse {
  items: CustomerPackSummary[]
  total: number
  page: number
  page_size: number
  investigation_id: number
}

export interface ClosureValidation {
  status: 'OK' | 'BLOCKED'
  reason_codes: string[]
  missing_fields: string[]
  checked_at_utc: string
}

export const investigationsApi = {
  list: (page = 1, size = 10, status?: string) => {
    const params = new URLSearchParams({ page: String(page), size: String(size) })
    if (status) params.set('status', status)
    return api.get<PaginatedResponse<Investigation>>(`/api/v1/investigations?${params}`)
  },
  create: (data: InvestigationCreate) => 
    api.post<Investigation>('/api/v1/investigations', data),
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
  
  // ============ Stage 1 Endpoints ============
  
  /**
   * Get timeline events for an investigation.
   * Ordered by created_at DESC, id DESC.
   */
  getTimeline: (id: number, options?: { page?: number; page_size?: number; type?: string }) => {
    const params = new URLSearchParams()
    if (options?.page) params.set('page', String(options.page))
    if (options?.page_size) params.set('page_size', String(options.page_size))
    if (options?.type) params.set('type', options.type)
    return api.get<TimelineResponse>(`/api/v1/investigations/${id}/timeline?${params}`)
  },
  
  /**
   * Get comments for an investigation.
   * Ordered by created_at DESC, id DESC.
   */
  getComments: (id: number, options?: { page?: number; page_size?: number }) => {
    const params = new URLSearchParams()
    if (options?.page) params.set('page', String(options.page))
    if (options?.page_size) params.set('page_size', String(options.page_size))
    return api.get<CommentsResponse>(`/api/v1/investigations/${id}/comments?${params}`)
  },
  
  /**
   * Add a comment to an investigation.
   */
  addComment: (id: number, body: string) =>
    api.post<InvestigationComment>(`/api/v1/investigations/${id}/comments`, { body }),
  
  /**
   * Get customer pack summaries for an investigation.
   * Does NOT include full content for security.
   */
  getPacks: (id: number, options?: { page?: number; page_size?: number }) => {
    const params = new URLSearchParams()
    if (options?.page) params.set('page', String(options.page))
    if (options?.page_size) params.set('page_size', String(options.page_size))
    return api.get<PacksResponse>(`/api/v1/investigations/${id}/packs?${params}`)
  },
  
  /**
   * Generate a new customer pack for an investigation.
   */
  generatePack: (id: number, audience: string) =>
    api.post<CustomerPackSummary>(`/api/v1/investigations/${id}/customer-pack`, { audience }),
  
  /**
   * Get closure validation status for an investigation.
   * Returns OK or BLOCKED with reason codes.
   */
  getClosureValidation: (id: number) =>
    api.get<ClosureValidation>(`/api/v1/investigations/${id}/closure-validation`),
}

export const standardsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Standard>>(`/api/v1/standards/?page=${page}&page_size=${size}`),
  get: (id: number) => 
    api.get<Standard & { clauses: Clause[] }>(`/api/v1/standards/${id}`),
  getClauses: (standardId: number) => 
    api.get<Clause[]>(`/api/v1/standards/${standardId}/clauses/`),
  getControls: (standardId: number) => 
    api.get<ControlListItem[]>(`/api/v1/standards/${standardId}/controls`),
  getComplianceScore: (standardId: number) => 
    api.get<ComplianceScore>(`/api/v1/standards/${standardId}/compliance-score`),
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
  list: (page = 1, size = 10, status?: string, source_type?: string, source_id?: number) => 
    api.get<PaginatedResponse<Action>>(`/api/v1/actions/?page=${page}&size=${size}${status ? `&status=${status}` : ''}${source_type ? `&source_type=${source_type}` : ''}${source_id ? `&source_id=${source_id}` : ''}`),
  /**
   * Create a new action linked to a source entity.
   */
  create: (data: ActionCreate) => 
    api.post<Action>('/api/v1/actions', data),
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

// ============ Planet Mark Types ============

export interface CarbonReportingYear {
  id: number
  year: number
  baseline_year: boolean
  total_emissions_tco2e: number
  scope1_emissions: number
  scope2_emissions: number
  scope3_emissions: number
  reduction_target_pct?: number
  status: 'draft' | 'in_progress' | 'submitted' | 'verified'
  certification_status?: string
  created_at: string
}

export interface EmissionSource {
  id: number
  year_id: number
  scope: 1 | 2 | 3
  category: string
  source_name: string
  quantity: number
  unit: string
  emission_factor: number
  calculated_tco2e: number
}

export interface ImprovementAction {
  id: number
  year_id: number
  title: string
  description: string
  target_reduction_tco2e: number
  status: 'planned' | 'in_progress' | 'completed' | 'cancelled'
  due_date?: string
}

export interface Scope3Category {
  category_number: number
  category_name: string
  emissions_tco2e: number
  percentage: number
  data_quality: 'high' | 'medium' | 'low'
}

export interface CarbonDashboard {
  current_year: number
  total_emissions: number
  reduction_vs_baseline: number
  scope1_pct: number
  scope2_pct: number
  scope3_pct: number
  certification_status: string
  years: CarbonReportingYear[]
}

/**
 * Planet Mark Carbon Management API client.
 * Endpoints: /api/v1/planet-mark/*
 */
export const planetMarkApi = {
  /**
   * Get carbon management dashboard summary.
   */
  getDashboard: () =>
    api.get<CarbonDashboard>('/api/v1/planet-mark/dashboard'),

  /**
   * List all carbon reporting years.
   */
  listYears: () =>
    api.get<CarbonReportingYear[]>('/api/v1/planet-mark/years'),

  /**
   * Get detailed data for a specific reporting year.
   */
  getYear: (yearId: number) =>
    api.get<CarbonReportingYear>(`/api/v1/planet-mark/years/${yearId}`),

  /**
   * List emission sources for a year.
   */
  listSources: (yearId: number) =>
    api.get<EmissionSource[]>(`/api/v1/planet-mark/years/${yearId}/sources`),

  /**
   * Get Scope 3 category breakdown for a year.
   */
  getScope3: (yearId: number) =>
    api.get<Scope3Category[]>(`/api/v1/planet-mark/years/${yearId}/scope3`),

  /**
   * List improvement actions for a year.
   */
  listActions: (yearId: number) =>
    api.get<ImprovementAction[]>(`/api/v1/planet-mark/years/${yearId}/actions`),

  /**
   * Get certification status for a year.
   */
  getCertification: (yearId: number) =>
    api.get<{ status: string; evidence_checklist: Record<string, boolean> }>(
      `/api/v1/planet-mark/years/${yearId}/certification`
    ),

  /**
   * Add an emission source to a reporting year.
   */
  addEmissionSource: (yearId: number, data: {
    source_name: string
    source_category: string
    scope: string
    activity_type: string
    activity_value: number
    activity_unit: string
    data_quality_level?: string
    data_source?: string
  }) =>
    api.post<{ id: number; co2e_tonnes: number; message: string }>(
      `/api/v1/planet-mark/years/${yearId}/sources`, data
    ),

  /**
   * Create a SMART improvement action for a reporting year.
   */
  createAction: (yearId: number, data: {
    action_title: string
    specific: string
    measurable: string
    achievable_owner: string
    time_bound: string
    expected_reduction_pct?: number
  }) =>
    api.post<{ id: number; action_id: string; message: string }>(
      `/api/v1/planet-mark/years/${yearId}/actions`, data
    ),
}

// ============ UVDB Achilles Types ============

export interface UVDBSection {
  section_number: number
  title: string
  description: string
  question_count: number
  weight: number
}

export interface UVDBQuestion {
  id: number
  section_number: number
  question_number: string
  question_text: string
  question_type: 'yes_no' | 'text' | 'numeric' | 'date' | 'file'
  is_mandatory: boolean
  guidance?: string
}

export interface UVDBAudit {
  id: number
  reference_number: string
  audit_year: number
  status: 'draft' | 'in_progress' | 'submitted' | 'verified'
  percentage_score?: number
  total_questions: number
  answered_questions: number
  created_at: string
  submitted_at?: string
}

export interface UVDBAuditResponse {
  id: number
  audit_id: number
  question_id: number
  response_value: string
  evidence_file_id?: number
  notes?: string
}

export interface UVDBDashboard {
  current_audit?: UVDBAudit
  historical_scores: { year: number; score: number }[]
  section_scores: { section: string; score: number }[]
  total_audits: number
  average_score: number
}

/**
 * UVDB Achilles Audit API client.
 * Endpoints: /api/v1/uvdb/*
 */
export const uvdbApi = {
  /**
   * Get UVDB dashboard summary.
   */
  getDashboard: () =>
    api.get<UVDBDashboard>('/api/v1/uvdb/dashboard'),

  /**
   * Get complete UVDB B2 protocol structure.
   */
  getProtocol: () =>
    api.get<{ sections: UVDBSection[]; total_questions: number }>('/api/v1/uvdb/protocol'),

  /**
   * List all UVDB sections.
   */
  listSections: () =>
    api.get<UVDBSection[]>('/api/v1/uvdb/sections'),

  /**
   * Get questions for a specific section.
   */
  getSectionQuestions: (sectionNumber: number) =>
    api.get<UVDBQuestion[]>(`/api/v1/uvdb/sections/${sectionNumber}/questions`),

  /**
   * List UVDB audits.
   */
  listAudits: (page = 1, size = 10) =>
    api.get<PaginatedResponse<UVDBAudit>>(`/api/v1/uvdb/audits?page=${page}&size=${size}`),

  /**
   * Get a specific audit by ID.
   */
  getAudit: (auditId: number) =>
    api.get<UVDBAudit>(`/api/v1/uvdb/audits/${auditId}`),

  /**
   * Get responses for an audit.
   */
  getAuditResponses: (auditId: number) =>
    api.get<UVDBAuditResponse[]>(`/api/v1/uvdb/audits/${auditId}/responses`),

  /**
   * Get ISO cross-mapping for UVDB sections.
   */
  getISOMapping: () =>
    api.get<{ mappings: { uvdb_section: string; iso_clauses: string[] }[] }>(
      '/api/v1/uvdb/iso-mapping'
    ),

  /**
   * Create a new UVDB audit.
   */
  createAudit: (data: {
    company_name: string
    audit_type?: string
    audit_scope?: string
    audit_date?: string
    lead_auditor?: string
  }) =>
    api.post<{ id: number; audit_reference: string; message: string }>(
      '/api/v1/uvdb/audits', data
    ),
}

// ============ User API ============

// User type for search results
export interface UserSearchResult {
  id: number
  email: string
  full_name: string
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
  created_at: string
  roles: RoleDetail[]
}

export interface RoleDetail {
  id: number
  name: string
  description?: string
  permissions: string[]
  is_system_role: boolean
}

export interface UserCreatePayload {
  email: string
  password: string
  first_name: string
  last_name: string
  department?: string
  phone?: string
  job_title?: string
  role_ids?: number[]
}

export interface UserUpdatePayload {
  first_name?: string
  last_name?: string
  department?: string
  phone?: string
  job_title?: string
  is_active?: boolean
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

export const usersApi = {
  search: (query: string) =>
    api.get<UserSearchResult[]>(`/api/v1/users/search/?q=${encodeURIComponent(query)}`),
  list: (page = 1, size = 50, params?: { search?: string; department?: string; is_active?: boolean }) => {
    const sp = new URLSearchParams({ page: String(page), page_size: String(size) })
    if (params?.search) sp.set('search', params.search)
    if (params?.department) sp.set('department', params.department)
    if (params?.is_active !== undefined) sp.set('is_active', String(params.is_active))
    return api.get<PaginatedResponse<UserDetail>>(`/api/v1/users?${sp}`)
  },
  get: (id: number) =>
    api.get<UserDetail>(`/api/v1/users/${id}`),
  create: (data: UserCreatePayload) =>
    api.post<UserDetail>('/api/v1/users', data),
  update: (id: number, data: UserUpdatePayload) =>
    api.patch<UserDetail>(`/api/v1/users/${id}`, data),
  delete: (id: number) =>
    api.delete<void>(`/api/v1/users/${id}`),
  listRoles: () =>
    api.get<RoleDetail[]>('/api/v1/users/roles'),
  createRole: (data: RoleCreatePayload) =>
    api.post<RoleDetail>('/api/v1/users/roles', data),
  updateRole: (id: number, data: RoleUpdatePayload) =>
    api.patch<RoleDetail>(`/api/v1/users/roles/${id}`, data),
}

// ============ Audit Trail API ============

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

export const auditTrailApi = {
  list: (params?: { entity_type?: string; action?: string; user_id?: number; date_from?: string; date_to?: string; page?: number; per_page?: number }) => {
    const sp = new URLSearchParams()
    if (params?.entity_type) sp.set('entity_type', params.entity_type)
    if (params?.action) sp.set('action', params.action)
    if (params?.user_id) sp.set('user_id', String(params.user_id))
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    sp.set('page', String(params?.page || 1))
    sp.set('per_page', String(params?.per_page || 50))
    return api.get<{ items: AuditLogEntry[]; total: number; page: number; per_page: number }>(`/api/v1/audit-trail?${sp}`)
  },
  getEntry: (id: number) =>
    api.get<AuditLogEntry>(`/api/v1/audit-trail/${id}`),
  getByEntity: (entityType: string, entityId: string) =>
    api.get<AuditLogEntry[]>(`/api/v1/audit-trail/entity/${entityType}/${entityId}`),
  getByUser: (userId: number, days = 30) =>
    api.get<AuditLogEntry[]>(`/api/v1/audit-trail/user/${userId}?days=${days}`),
  verify: () =>
    api.post<AuditVerification>('/api/v1/audit-trail/verify'),
  exportLog: (params: { format?: string; date_from?: string; date_to?: string; entity_type?: string; reason?: string }) =>
    api.post<{ export_id: number; entries_count: number; file_hash: string; data?: unknown[] }>('/api/v1/audit-trail/export', params),
  getStats: (days = 30) =>
    api.get<Record<string, unknown>>(`/api/v1/audit-trail/stats?days=${days}`),
}

// ============ Risk Register API ============

export interface RiskEntry {
  id: number
  title: string
  description?: string
  category?: string
  risk_owner?: string
  status: string
  likelihood?: number
  impact?: number
  risk_score?: number
  residual_likelihood?: number
  residual_impact?: number
  residual_score?: number
  treatment_strategy?: string
  review_date?: string
  created_at: string
  updated_at?: string
}

export interface RiskHeatmapData {
  cells: { likelihood: number; impact: number; count: number; risks: { id: number; title: string }[] }[]
}

export interface RiskSummary {
  total_risks: number
  critical: number
  high: number
  medium: number
  low: number
  by_category: Record<string, number>
}

export const riskRegisterApi = {
  list: (params?: { skip?: number; limit?: number; status?: string; category?: string; search?: string }) => {
    const sp = new URLSearchParams()
    if (params?.skip != null) sp.set('skip', String(params.skip))
    if (params?.limit != null) sp.set('limit', String(params.limit))
    if (params?.status) sp.set('status', params.status)
    if (params?.category) sp.set('category', params.category)
    if (params?.search) sp.set('search', params.search)
    return api.get<PaginatedResponse<RiskEntry>>(`/api/v1/risk-register?${sp}`)
  },
  create: (data: Partial<RiskEntry>) =>
    api.post<RiskEntry>('/api/v1/risk-register', data),
  get: (id: number) =>
    api.get<RiskEntry>(`/api/v1/risk-register/${id}`),
  update: (id: number, data: Partial<RiskEntry>) =>
    api.put<RiskEntry>(`/api/v1/risk-register/${id}`, data),
  delete: (id: number) =>
    api.delete<void>(`/api/v1/risk-register/${id}`),
  assess: (id: number, scores: { likelihood: number; impact: number }) =>
    api.post<RiskEntry>(`/api/v1/risk-register/${id}/assess`, scores),
  getHeatmap: () =>
    api.get<RiskHeatmapData>('/api/v1/risk-register/heatmap'),
  getSummary: () =>
    api.get<RiskSummary>('/api/v1/risk-register/summary'),
  getTrends: (days = 90) =>
    api.get<unknown>(`/api/v1/risk-register/trends?days=${days}`),
  getBowtie: (id: number) =>
    api.get<unknown>(`/api/v1/risk-register/${id}/bowtie`),
  addBowtieElement: (id: number, data: Record<string, unknown>) =>
    api.post<unknown>(`/api/v1/risk-register/${id}/bowtie`, data),
  deleteBowtieElement: (id: number, elementId: number) =>
    api.delete<void>(`/api/v1/risk-register/${id}/bowtie/${elementId}`),
  listControls: () =>
    api.get<unknown[]>('/api/v1/risk-register/controls'),
  createControl: (data: Record<string, unknown>) =>
    api.post<unknown>('/api/v1/risk-register/controls', data),
  linkControl: (riskId: number, controlId: number) =>
    api.post<void>(`/api/v1/risk-register/${riskId}/controls/${controlId}`),
  getKRIDashboard: () =>
    api.get<unknown>('/api/v1/risk-register/kris/dashboard'),
  createKRI: (data: Record<string, unknown>) =>
    api.post<unknown>('/api/v1/risk-register/kris', data),
  updateKRIValue: (id: number, value: number) =>
    api.post<unknown>(`/api/v1/risk-register/kris/${id}/value`, { value }),
  getKRIHistory: (id: number) =>
    api.get<unknown>(`/api/v1/risk-register/kris/${id}/history`),
  getAppetiteStatements: () =>
    api.get<unknown[]>('/api/v1/risk-register/appetite/statements'),
}

// ============ Signatures API ============

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
  signers: { id: number; email: string; name: string; role: string; order: number; status: string; signed_at?: string; declined_at?: string }[]
}

export const signaturesApi = {
  list: (status?: string, limit = 50) => {
    const sp = new URLSearchParams({ limit: String(limit) })
    if (status) sp.set('status', status)
    return api.get<SignatureRequestEntry[]>(`/api/v1/signatures/requests?${sp}`)
  },
  get: (id: number) =>
    api.get<SignatureRequestEntry>(`/api/v1/signatures/requests/${id}`),
  create: (data: { title: string; description?: string; document_type: string; document_id?: string; workflow_type?: string; require_all?: boolean; expires_in_days?: number; signers: { email: string; name: string; role?: string; order?: number }[] }) =>
    api.post<SignatureRequestEntry>('/api/v1/signatures/requests', data),
  send: (id: number) =>
    api.post<{ status: string; reference: string }>(`/api/v1/signatures/requests/${id}/send`),
  void: (id: number, reason?: string) =>
    api.post<{ status: string; reference: string }>(`/api/v1/signatures/requests/${id}/void`, { reason }),
  getPending: () =>
    api.get<SignatureRequestEntry[]>('/api/v1/signatures/requests/pending'),
  getAuditLog: (id: number) =>
    api.get<unknown[]>(`/api/v1/signatures/requests/${id}/audit-log`),
  getStats: () =>
    api.get<{ requests_by_status: Record<string, number>; total_signatures: number; requests_this_month: number }>('/api/v1/signatures/stats'),
  listTemplates: () =>
    api.get<unknown[]>('/api/v1/signatures/templates'),
  createTemplate: (data: { name: string; description?: string; signer_roles?: unknown[]; workflow_type?: string }) =>
    api.post<unknown>('/api/v1/signatures/templates', data),
}

// ============ AI Intelligence API ============

export const aiApi = {
  analyzeText: (text: string, analysisType?: string) =>
    api.post<unknown>('/api/v1/ai/analyze-text', { text, analysis_type: analysisType }),
  getPredictions: (module?: string) =>
    api.get<unknown>(`/api/v1/ai/predictions${module ? `?module=${module}` : ''}`),
  getAnomalies: (module?: string, days?: number) =>
    api.get<unknown>(`/api/v1/ai/anomalies?${new URLSearchParams({ ...(module ? { module } : {}), ...(days ? { days: String(days) } : {}) })}`),
  auditAssistant: (query: string, context?: Record<string, unknown>) =>
    api.post<unknown>('/api/v1/ai/audit-assistant', { query, context }),
  getRecommendations: (module?: string) =>
    api.get<unknown>(`/api/v1/ai/recommendations${module ? `?module=${module}` : ''}`),
  getSentiment: (text: string) =>
    api.post<unknown>('/api/v1/ai/sentiment', { text }),
  classifyRisk: (description: string) =>
    api.post<unknown>('/api/v1/ai/classify-risk', { description }),
  getDashboard: () =>
    api.get<unknown>('/api/v1/ai/dashboard'),
  generateAuditQuestions: (standard: string, clause: string, context?: string) =>
    api.post<unknown[]>('/api/v1/ai/audit/generate-questions', { standard, clause, context }),
  generateAuditChecklist: (standard: string, scopeClauses?: string[]) =>
    api.post<unknown[]>('/api/v1/ai/audit/generate-checklist', { standard, scope_clauses: scopeClauses }),
}

// ============ Analytics API ============

export const analyticsApi = {
  getKPIs: (timeRange?: string) =>
    api.get<unknown>(`/api/v1/analytics/kpis${timeRange ? `?time_range=${timeRange}` : ''}`),
  getTrends: (dataSource: string, timeRange?: string) =>
    api.get<unknown>(`/api/v1/analytics/trends/${dataSource}${timeRange ? `?time_range=${timeRange}` : ''}`),
  getBenchmarks: (industry?: string) =>
    api.get<unknown>(`/api/v1/analytics/benchmarks${industry ? `?industry=${industry}` : ''}`),
  getExecutiveSummary: (timeRange?: string) =>
    api.get<unknown>(`/api/v1/analytics/reports/executive-summary${timeRange ? `?time_range=${timeRange}` : ''}`),
  getNonComplianceCosts: (timeRange?: string) =>
    api.get<unknown>(`/api/v1/analytics/costs/non-compliance${timeRange ? `?time_range=${timeRange}` : ''}`),
  getROI: () =>
    api.get<unknown>('/api/v1/analytics/roi'),
  getCostBreakdown: (timeRange?: string) =>
    api.get<unknown>(`/api/v1/analytics/costs/breakdown${timeRange ? `?time_range=${timeRange}` : ''}`),
  getDrillDown: (dataSource: string, dimension: string, value: string, timeRange?: string) =>
    api.get<unknown>(`/api/v1/analytics/drill-down/${dataSource}?dimension=${dimension}&value=${value}${timeRange ? `&time_range=${timeRange}` : ''}`),
  forecast: (dataSource: string, metric: string, periodsAhead?: number) =>
    api.post<unknown>('/api/v1/analytics/forecast', { data_source: dataSource, metric, periods_ahead: periodsAhead || 12, confidence_level: 0.95 }),
  listDashboards: () =>
    api.get<{ dashboards: Array<{ id: number; name: string; description?: string; icon?: string; color?: string; is_default?: boolean; widget_count?: number; updated_at?: string }> }>('/api/v1/analytics/dashboards'),
  getDashboard: (id: number) =>
    api.get<{ id: number; name: string; description?: string; widgets: Array<{ id: number; widget_type: string; title: string; data_source: string; metric: string; grid_x: number; grid_y: number; grid_w: number; grid_h: number }> }>(`/api/v1/analytics/dashboards/${id}`),
  createDashboard: (data: { name: string; description?: string; widgets?: unknown[] }) =>
    api.post<{ id: number; name: string }>('/api/v1/analytics/dashboards', data),
  updateDashboard: (id: number, data: { name?: string; description?: string; layout?: unknown }) =>
    api.put<{ id: number; name: string }>(`/api/v1/analytics/dashboards/${id}`, data),
  deleteDashboard: (id: number) =>
    api.delete<{ success: boolean }>(`/api/v1/analytics/dashboards/${id}`),
  getWidgetData: (widgetId: number, timeRange?: string) =>
    api.get<unknown>(`/api/v1/analytics/widgets/${widgetId}/data${timeRange ? `?time_range=${timeRange}` : ''}`),
}

// ============ Notifications API ============

export interface NotificationEntry {
  id: number
  type: string
  priority: string
  title: string
  message: string
  entity_type?: string
  entity_id?: string
  action_url?: string
  sender_id?: number
  is_read: boolean
  created_at: string
}

export const notificationsApi = {
  list: (params?: { page?: number; page_size?: number; unread_only?: boolean }) => {
    const sp = new URLSearchParams()
    if (params?.page) sp.set('page', String(params.page))
    if (params?.page_size) sp.set('page_size', String(params.page_size))
    if (params?.unread_only) sp.set('unread_only', 'true')
    return api.get<{ items: NotificationEntry[]; total: number; unread_count: number }>(`/api/v1/notifications?${sp}`)
  },
  getUnreadCount: () =>
    api.get<{ unread_count: number }>('/api/v1/notifications/unread-count'),
  markRead: (id: number) =>
    api.post<{ success: boolean }>(`/api/v1/notifications/${id}/read`),
  markAllRead: () =>
    api.post<{ success: boolean }>('/api/v1/notifications/read-all'),
  delete: (id: number) =>
    api.delete<{ success: boolean }>(`/api/v1/notifications/${id}`),
  getPreferences: () =>
    api.get<Record<string, unknown>>('/api/v1/notifications/preferences'),
  updatePreferences: (data: Record<string, unknown>) =>
    api.put<{ success: boolean }>('/api/v1/notifications/preferences', data),
}

// ============ Compliance API ============

export interface AutoTagResult {
  clause_id: string
  clause_number: string
  title: string
  standard: string
  confidence: number
  linked_by: string
}

export interface EvidenceLinkRecord {
  id: number
  entity_type: string
  entity_id: string
  clause_id: string
  linked_by: string
  confidence: number | null
  title: string | null
  notes: string | null
  created_at: string
  created_by_email: string | null
}

export const complianceApi = {
  listClauses: (standard?: string, search?: string) => {
    const sp = new URLSearchParams()
    if (standard) sp.set('standard', standard)
    if (search) sp.set('search', search)
    return api.get<unknown[]>(`/api/v1/compliance/clauses?${sp}`)
  },
  autoTag: (content: string, useAi = false) =>
    api.post<AutoTagResult[]>('/api/v1/compliance/auto-tag', { content, use_ai: useAi }),
  linkEvidence: (data: {
    entity_type: string
    entity_id: string
    clause_ids: string[]
    linked_by?: string
    confidence?: number
    title?: string
    notes?: string
  }) =>
    api.post<{ status: string; message: string; links: unknown[] }>('/api/v1/compliance/evidence/link', data),
  listEvidenceLinks: (params?: { entity_type?: string; entity_id?: string; clause_id?: string; page?: number; size?: number }) => {
    const sp = new URLSearchParams()
    if (params?.entity_type) sp.set('entity_type', params.entity_type)
    if (params?.entity_id) sp.set('entity_id', params.entity_id)
    if (params?.clause_id) sp.set('clause_id', params.clause_id)
    if (params?.page) sp.set('page', String(params.page))
    if (params?.size) sp.set('size', String(params.size))
    return api.get<EvidenceLinkRecord[]>(`/api/v1/compliance/evidence/links?${sp}`)
  },
  deleteEvidenceLink: (linkId: number) =>
    api.delete<{ status: string }>(`/api/v1/compliance/evidence/link/${linkId}`),
  getCoverage: (standard?: string) =>
    api.get<Record<string, unknown>>(`/api/v1/compliance/coverage${standard ? `?standard=${standard}` : ''}`),
  getGaps: (standard?: string) =>
    api.get<{ total_gaps: number; gap_clauses: unknown[] }>(`/api/v1/compliance/gaps${standard ? `?standard=${standard}` : ''}`),
  getReport: (standard?: string) =>
    api.get<unknown>(`/api/v1/compliance/report${standard ? `?standard=${standard}` : ''}`),
  listStandards: () =>
    api.get<unknown[]>('/api/v1/compliance/standards'),
}

// ============ Compliance Automation API ============

export const complianceAutomationApi = {
  listRegulatoryUpdates: (params?: { source?: string; impact?: string; reviewed?: boolean }) => {
    const sp = new URLSearchParams()
    if (params?.source) sp.set('source', params.source)
    if (params?.impact) sp.set('impact', params.impact)
    if (params?.reviewed !== undefined) sp.set('reviewed', String(params.reviewed))
    return api.get<{ updates: unknown[]; total: number; unreviewed: number }>(`/api/v1/compliance-automation/regulatory-updates?${sp}`)
  },
  reviewUpdate: (updateId: number, data?: { requires_action?: boolean; action_notes?: string }) => {
    const sp = new URLSearchParams()
    if (data?.requires_action !== undefined) sp.set('requires_action', String(data.requires_action))
    if (data?.action_notes) sp.set('action_notes', data.action_notes)
    return api.post<unknown>(`/api/v1/compliance-automation/regulatory-updates/${updateId}/review?${sp}`)
  },
  runGapAnalysis: (params?: { regulatory_update_id?: number; standard_id?: number }) => {
    const sp = new URLSearchParams()
    if (params?.regulatory_update_id) sp.set('regulatory_update_id', String(params.regulatory_update_id))
    if (params?.standard_id) sp.set('standard_id', String(params.standard_id))
    return api.post<unknown>(`/api/v1/compliance-automation/gap-analysis/run?${sp}`)
  },
  listGapAnalyses: (status?: string) => {
    const sp = new URLSearchParams()
    if (status) sp.set('status_filter', status)
    return api.get<{ analyses: unknown[]; total: number }>(`/api/v1/compliance-automation/gap-analyses?${sp}`)
  },
  listCertificates: (params?: { certificate_type?: string; entity_type?: string; status?: string; expiring_within_days?: number }) => {
    const sp = new URLSearchParams()
    if (params?.certificate_type) sp.set('certificate_type', params.certificate_type)
    if (params?.entity_type) sp.set('entity_type', params.entity_type)
    if (params?.status) sp.set('status_filter', params.status)
    if (params?.expiring_within_days) sp.set('expiring_within_days', String(params.expiring_within_days))
    return api.get<{ certificates: unknown[]; total: number }>(`/api/v1/compliance-automation/certificates?${sp}`)
  },
  getExpiringCertificates: () =>
    api.get<{ expired: number; expiring_7_days: number; expiring_30_days: number; expiring_90_days: number; total_critical: number }>('/api/v1/compliance-automation/certificates/expiring-summary'),
  addCertificate: (data: {
    name: string
    certificate_type: string
    entity_type: string
    entity_id: string
    entity_name?: string
    issuing_body?: string
    issue_date: string
    expiry_date: string
    is_critical?: boolean
    notes?: string
  }) =>
    api.post<unknown>('/api/v1/compliance-automation/certificates', data),
  listScheduledAudits: (params?: { upcoming_days?: number; overdue?: boolean }) => {
    const sp = new URLSearchParams()
    if (params?.upcoming_days) sp.set('upcoming_days', String(params.upcoming_days))
    if (params?.overdue !== undefined) sp.set('overdue', String(params.overdue))
    return api.get<{ audits: unknown[]; total: number }>(`/api/v1/compliance-automation/scheduled-audits?${sp}`)
  },
  scheduleAudit: (data: {
    name: string
    audit_type: string
    frequency: string
    next_due_date: string
    description?: string
    department?: string
    standard_ids?: string[]
  }) =>
    api.post<unknown>('/api/v1/compliance-automation/scheduled-audits', data),
  getComplianceScore: (params?: { scope_type?: string; scope_id?: string }) => {
    const sp = new URLSearchParams()
    if (params?.scope_type) sp.set('scope_type', params.scope_type)
    if (params?.scope_id) sp.set('scope_id', params.scope_id)
    return api.get<Record<string, unknown>>(`/api/v1/compliance-automation/score?${sp}`)
  },
  getComplianceTrend: (params?: { scope_type?: string; months?: number }) => {
    const sp = new URLSearchParams()
    if (params?.scope_type) sp.set('scope_type', params.scope_type)
    if (params?.months) sp.set('months', String(params.months))
    return api.get<{ trend: unknown[]; period_months: number }>(`/api/v1/compliance-automation/score/trend?${sp}`)
  },
  listRiddorSubmissions: (status?: string) => {
    const sp = new URLSearchParams()
    if (status) sp.set('status_filter', status)
    return api.get<{ submissions: unknown[]; total: number }>(`/api/v1/compliance-automation/riddor/submissions?${sp}`)
  },
  checkRiddor: (incidentData: Record<string, unknown>) =>
    api.post<{ is_riddor: boolean; riddor_types: string[]; deadline: string | null; submission_url: string | null }>('/api/v1/compliance-automation/riddor/check', incidentData),
  prepareRiddor: (incidentId: number, riddorType: string) => {
    const sp = new URLSearchParams({ riddor_type: riddorType })
    return api.post<unknown>(`/api/v1/compliance-automation/riddor/prepare/${incidentId}?${sp}`)
  },
  submitRiddor: (incidentId: number) =>
    api.post<unknown>(`/api/v1/compliance-automation/riddor/submit/${incidentId}`),
}

// ============ IMS Dashboard API ============

export interface IMSDashboardResponse {
  generated_at: string
  overall_compliance: number
  standards: {
    standard_id: number
    standard_code: string
    standard_name: string
    full_name: string
    version: string
    total_controls: number
    implemented_count: number
    partial_count: number
    not_implemented_count: number
    compliance_percentage: number
    setup_required: boolean
  }[]
  isms: {
    assets: { total: number; critical: number }
    controls: { total: number; applicable: number; implemented: number; implementation_percentage: number }
    risks: { open: number; high_critical: number }
    incidents: { open: number; last_30_days: number }
    suppliers: { high_risk: number }
    compliance_score: number
    domains: { domain: string; total: number; implemented: number; percentage: number }[]
    recent_incidents: { id: string; title: string; incident_type: string; severity: string; status: string; date: string }[]
  } | null
  isms_error?: string
  uvdb: {
    total_audits: number
    active_audits: number
    completed_audits: number
    average_score: number
    latest_score: number | null
    status: string
  } | null
  uvdb_error?: string
  planet_mark: {
    status: string
    current_year: number | null
    total_emissions: number | null
    certification_status: string | null
    reduction_vs_previous: number | null
    scope1: number
    scope2: number
    scope3: number
  } | null
  planet_mark_error?: string
  compliance_coverage: {
    total_clauses: number
    covered_clauses: number
    coverage_percentage: number
    gaps: number
    total_evidence_links: number
  } | null
  compliance_coverage_error?: string
  audit_schedule: {
    id: number
    reference_number: string
    title: string | null
    status: string
    scheduled_date: string | null
    due_date: string | null
  }[]
  audit_schedule_error?: string
  standards_error?: string
}

export const imsDashboardApi = {
  getDashboard: () =>
    api.get<IMSDashboardResponse>('/api/v1/ims/dashboard'),
}

// ============ Global Search API ============

export const searchApi = {
  search: (query: string, filters?: { module?: string; type?: string; date_from?: string; date_to?: string }) => {
    const sp = new URLSearchParams({ q: query })
    if (filters?.module) sp.set('module', filters.module)
    if (filters?.type) sp.set('type', filters.type)
    if (filters?.date_from) sp.set('date_from', filters.date_from)
    if (filters?.date_to) sp.set('date_to', filters.date_to)
    return api.get<{ results: unknown[]; total: number; facets?: Record<string, unknown> }>(`/api/v1/search?${sp}`)
  },
}

// ============ Evidence Assets API ============

export interface EvidenceAsset {
  id: number
  storage_key: string
  original_filename?: string
  content_type: string
  file_size_bytes?: number
  checksum_sha256?: string
  asset_type: string
  source_module: string
  source_id: number
  linked_investigation_id?: number
  title?: string
  description?: string
  captured_at?: string
  captured_by_role?: string
  latitude?: number
  longitude?: number
  location_description?: string
  render_hint?: string
  thumbnail_storage_key?: string
  metadata_json?: Record<string, unknown>
  visibility: string
  contains_pii: boolean
  redaction_required: boolean
  retention_policy: string
  retention_expires_at?: string
  created_at: string
  updated_at: string
  created_by_id?: number
  updated_by_id?: number
}

export interface EvidenceAssetListResponse {
  items: EvidenceAsset[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface EvidenceAssetUploadResponse {
  id: number
  storage_key: string
  original_filename: string
  content_type: string
  file_size_bytes: number
  upload_url?: string
  message: string
}

export interface SignedUrlResponse {
  asset_id: number
  signed_url: string
  expires_in_seconds: number
  content_type: string
  filename?: string
}

export const evidenceAssetsApi = {
  /**
   * List evidence assets with filtering.
   * For investigations: source_module=investigation, source_id=investigation_id
   */
  list: (options?: {
    page?: number
    page_size?: number
    source_module?: string
    source_id?: number
    asset_type?: string
    linked_investigation_id?: number
  }) => {
    const params = new URLSearchParams()
    if (options?.page) params.set('page', String(options.page))
    if (options?.page_size) params.set('page_size', String(options.page_size))
    if (options?.source_module) params.set('source_module', options.source_module)
    if (options?.source_id) params.set('source_id', String(options.source_id))
    if (options?.asset_type) params.set('asset_type', options.asset_type)
    if (options?.linked_investigation_id) params.set('linked_investigation_id', String(options.linked_investigation_id))
    return api.get<EvidenceAssetListResponse>(`/api/v1/evidence-assets?${params}`)
  },

  /**
   * Get a single evidence asset by ID.
   */
  get: (assetId: number) =>
    api.get<EvidenceAsset>(`/api/v1/evidence-assets/${assetId}`),

  /**
   * Upload a new evidence asset.
   * Uses multipart/form-data for file upload.
   */
  upload: (file: File, data: {
    source_module: string
    source_id: number
    title?: string
    description?: string
    visibility?: string
    contains_pii?: boolean
    redaction_required?: boolean
  }) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('source_module', data.source_module)
    formData.append('source_id', String(data.source_id))
    if (data.title) formData.append('title', data.title)
    if (data.description) formData.append('description', data.description)
    if (data.visibility) formData.append('visibility', data.visibility)
    if (data.contains_pii !== undefined) formData.append('contains_pii', String(data.contains_pii))
    if (data.redaction_required !== undefined) formData.append('redaction_required', String(data.redaction_required))
    
    return api.post<EvidenceAssetUploadResponse>('/api/v1/evidence-assets/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: UPLOAD_TIMEOUT_MS, // Extended timeout for file uploads to Azure Blob Storage
    })
  },

  /**
   * Link an evidence asset to an investigation.
   */
  linkToInvestigation: (assetId: number, investigationId: number) =>
    api.post<EvidenceAsset>(`/api/v1/evidence-assets/${assetId}/link-investigation?investigation_id=${investigationId}`),

  /**
   * Delete (soft delete) an evidence asset.
   */
  delete: (assetId: number) =>
    api.delete(`/api/v1/evidence-assets/${assetId}`),

  /**
   * Get a signed download URL for an evidence asset.
   */
  getSignedUrl: (assetId: number, expiresIn?: number) => {
    const params = new URLSearchParams()
    if (expiresIn) params.set('expires_in', String(expiresIn))
    return api.get<SignedUrlResponse>(`/api/v1/evidence-assets/${assetId}/signed-url?${params}`)
  },
}

// ============ Workflows ============

export const workflowsApi = {
  getPendingApprovals: () =>
    api.get<Record<string, unknown>[]>('/api/v1/workflows/approvals/pending'),
  approveRequest: (approvalId: number, data?: { comments?: string }) =>
    api.post(`/api/v1/workflows/approvals/${approvalId}/approve`, data),
  rejectRequest: (approvalId: number, data?: { comments?: string; reason?: string }) =>
    api.post(`/api/v1/workflows/approvals/${approvalId}/reject`, data),
  bulkApprove: (approvalIds: number[], data?: { comments?: string }) =>
    api.post('/api/v1/workflows/approvals/bulk-approve', { approval_ids: approvalIds, ...data }),
  listInstances: (params?: { page?: number; size?: number }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.size) sp.set('size', String(params.size));
    return api.get<{ items: Record<string, unknown>[]; total: number }>(`/api/v1/workflows/instances?${sp}`);
  },
  listTemplates: () =>
    api.get<Record<string, unknown>[]>('/api/v1/workflows/templates'),
  getStats: () =>
    api.get<Record<string, unknown>>('/api/v1/workflows/stats'),
  getDelegations: () =>
    api.get<Record<string, unknown>[]>('/api/v1/workflows/delegations'),
  setDelegation: (data: { delegate_to: number; entity_type?: string; start_date?: string; end_date?: string }) =>
    api.post('/api/v1/workflows/delegations', data),
  cancelDelegation: (delegationId: number) =>
    api.delete(`/api/v1/workflows/delegations/${delegationId}`),
}

// ============ Executive Dashboard ============

export interface ExecutiveDashboardData {
  generated_at: string
  period_days: number
  health_score: {
    score: number
    status: string
    color: string
    components: Record<string, number>
  }
  incidents: {
    total_in_period: number
    open: number
    by_severity: Record<string, number>
    sif_count: number
    psif_count: number
    critical_high: number
  }
  near_misses: {
    total_in_period: number
    previous_period: number
    trend_percent: number
    reporting_rate: string
  }
  complaints: {
    total_in_period: number
    open: number
    closed_in_period: number
    resolution_rate: number
  }
  rtas: {
    total_in_period: number
  }
  risks: {
    total_active: number
    by_level: Record<string, number>
    high_critical: number
    average_score: number
  }
  kris: {
    total_active: number
    by_status: Record<string, number>
    at_risk: number
    pending_alerts: number
  }
  compliance: {
    total_assigned: number
    completed: number
    overdue: number
    completion_rate: number
  }
  sla_performance: {
    total_tracked: number
    met: number
    breached: number
    compliance_rate: number
  }
  trends: {
    incidents_weekly: { week_start: string; count: number }[]
  }
  alerts: {
    type: string
    severity: string
    title: string
    triggered_at: string
  }[]
}

export const executiveDashboardApi = {
  getDashboard: (periodDays = 30) =>
    api.get<ExecutiveDashboardData>(`/api/v1/executive-dashboard?period_days=${periodDays}`),
  getSummary: () =>
    api.get<{ health_score: number; health_status: string; open_incidents: number; pending_actions: number; overdue_items: number; kri_alerts: number }>('/api/v1/executive-dashboard/summary'),
  getAlerts: () =>
    api.get<{ total: number; alerts: ExecutiveDashboardData['alerts'] }>('/api/v1/executive-dashboard/alerts'),
}

// ============ Report/Pack Capability Check ============

/**
 * Check if pack generation is available for an investigation.
 * Returns capability info for deterministic UI behavior.
 */
export interface PackCapability {
  canGenerate: boolean
  reason?: string
  lastError?: string
}

export async function checkPackCapability(investigationId: number): Promise<PackCapability> {
  try {
    // Try to hit the endpoint with a dry-run or just check if it returns 404/501
    // For now, we'll just try to get packs list - if that works, generation should too
    await investigationsApi.getPacks(investigationId, { page: 1, page_size: 1 })
    return { canGenerate: true }
  } catch (err: unknown) {
    const error = err as { response?: { status?: number } }
    if (error.response?.status === 404) {
      return { canGenerate: false, reason: 'Investigation not found or pack generation not available' }
    }
    if (error.response?.status === 501) {
      return { canGenerate: false, reason: 'Pack generation is not implemented in this environment' }
    }
    if (error.response?.status === 403) {
      return { canGenerate: false, reason: 'You do not have permission to generate packs' }
    }
    return { canGenerate: true } // Assume available, will fail on actual generate
  }
}

export default api
