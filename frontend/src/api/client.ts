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

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

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

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

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

export default api
