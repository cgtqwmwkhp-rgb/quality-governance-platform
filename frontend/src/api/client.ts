import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://qgp-staging-plantexpand.azurewebsites.net'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
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
      localStorage.removeItem('access_token')
      window.location.href = '/login'
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

// ============ API Functions ============
export const authApi = {
  login: (data: LoginRequest) => 
    api.post<LoginResponse>('/api/v1/auth/login', data),
}

export const incidentsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Incident>>(`/api/v1/incidents?page=${page}&size=${size}`),
  create: (data: IncidentCreate) => 
    api.post<Incident>('/api/v1/incidents', data),
  get: (id: number) => 
    api.get<Incident>(`/api/v1/incidents/${id}`),
}

export const rtasApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<RTA>>(`/api/v1/rtas?page=${page}&size=${size}`),
  create: (data: RTACreate) => 
    api.post<RTA>('/api/v1/rtas', data),
  get: (id: number) => 
    api.get<RTA>(`/api/v1/rtas/${id}`),
}

export const complaintsApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Complaint>>(`/api/v1/complaints?page=${page}&size=${size}`),
  create: (data: ComplaintCreate) => 
    api.post<Complaint>('/api/v1/complaints', data),
  get: (id: number) => 
    api.get<Complaint>(`/api/v1/complaints/${id}`),
}

export const policiesApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Policy>>(`/api/v1/policies?page=${page}&size=${size}`),
  create: (data: PolicyCreate) => 
    api.post<Policy>('/api/v1/policies', data),
  get: (id: number) => 
    api.get<Policy>(`/api/v1/policies/${id}`),
}

export const risksApi = {
  list: (page = 1, size = 10) => 
    api.get<PaginatedResponse<Risk>>(`/api/v1/risks?page=${page}&size=${size}`),
  create: (data: RiskCreate) => 
    api.post<Risk>('/api/v1/risks', data),
  get: (id: number) => 
    api.get<Risk>(`/api/v1/risks/${id}`),
}

export default api
