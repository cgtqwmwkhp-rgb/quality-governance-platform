import axios from 'axios'

// HARDCODED HTTPS - bypassing any potential env var issues
const HTTPS_API_BASE = 'https://app-qgp-prod.azurewebsites.net';

console.log('[Axios Client] Using API base:', HTTPS_API_BASE);

const api = axios.create({
  baseURL: HTTPS_API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

// CRITICAL: Enforce HTTPS on all requests at interceptor level
api.interceptors.request.use((config) => {
  // Log the request for debugging
  const fullUrl = config.baseURL + (config.url || '');
  console.log('[Axios] Request to:', fullUrl);
  
  // Force HTTPS on baseURL
  if (config.baseURL && !config.baseURL.startsWith('https://')) {
    config.baseURL = config.baseURL.replace(/^http:/, 'https:');
    if (!config.baseURL.startsWith('https://')) {
      config.baseURL = 'https://' + config.baseURL.replace(/^\/\//, '');
    }
    console.warn('[Axios] Forced HTTPS on baseURL:', config.baseURL);
  }
  
  // Force HTTPS on URL if it's absolute
  if (config.url && config.url.startsWith('http:')) {
    config.url = config.url.replace(/^http:/, 'https:');
    console.warn('[Axios] Forced HTTPS on URL:', config.url);
  }
  
  // Add auth token
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Only redirect to login if we're not already there and this is an auth failure
      // (not just a missing/invalid token for a specific endpoint)
      const currentPath = window.location.pathname
      const isLoginPage = currentPath === '/login' || currentPath === '/portal'
      const isAuthEndpoint = error.config?.url?.includes('/auth/')
      
      // Only clear token and redirect for auth-related 401s, not data endpoint 401s
      if (isAuthEndpoint && !isLoginPage) {
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }
      // For non-auth endpoints, just reject and let the component handle it
    }
    return Promise.reject(error)
  }
)

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
}

export const rtasApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<RTA>>(`/api/v1/rtas/?page=${page}&size=${size}`),
  create: (data: RTACreate) => 
    api.post<RTA>('/api/v1/rtas/', data),
  get: (id: number) => 
    api.get<RTA>(`/api/v1/rtas/${id}`),
}

export const complaintsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Complaint>>(`/api/v1/complaints/?page=${page}&size=${size}`),
  create: (data: ComplaintCreate) => 
    api.post<Complaint>('/api/v1/complaints/', data),
  get: (id: number) => 
    api.get<Complaint>(`/api/v1/complaints/${id}`),
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

export const investigationsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Investigation>>(`/api/v1/investigations/?page=${page}&size=${size}`),
  create: (data: InvestigationCreate) => 
    api.post<Investigation>('/api/v1/investigations/', data),
  get: (id: number) => 
    api.get<Investigation>(`/api/v1/investigations/${id}`),
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

export const actionsApi = {
  list: (page = 1, size = 10, status?: string) => 
    api.get<PaginatedResponse<Action>>(`/api/v1/actions/?page=${page}&size=${size}${status ? `&status=${status}` : ''}`),
  create: (data: ActionCreate) => 
    api.post<Action>('/api/v1/actions/', data),
  get: (id: number) => 
    api.get<Action>(`/api/v1/actions/${id}`),
  update: (id: number, data: Partial<Action>) => 
    api.patch<Action>(`/api/v1/actions/${id}`, data),
}

export default api
