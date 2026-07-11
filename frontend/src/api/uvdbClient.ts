/**
 * UVDB Achilles API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

// ============ UVDB Achilles Types ============

export interface UVDBSectionRecord {
  number: string
  title: string
  max_score: number
  question_count: number
  iso_mapping: Record<string, string>
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

export interface UVDBAuditListItem {
  id: number
  audit_reference: string
  company_name: string
  audit_type: string
  audit_date: string | null
  status: string
  percentage_score: number | null
  lead_auditor: string | null
}

export interface UVDBAuditResponse {
  id: number
  audit_id: number
  question_id: number
  response_value: string
  evidence_file_id?: number
  notes?: string
}

export interface UVDBDashboardResponse {
  summary: {
    total_audits: number
    active_audits: number
    completed_audits: number
    average_score: number
  }
  protocol: {
    name: string
    version: string
    sections: number
  }
  certification_alignment: Record<string, string>
}

export interface UVDBSectionsResponse {
  total_sections: number
  sections: UVDBSectionRecord[]
}

export interface UVDBAuditsResponse {
  total: number
  audits: UVDBAuditListItem[]
}

export interface UVDBIsoMappingRecord {
  uvdb_section: string
  uvdb_question: string
  uvdb_text: string
  iso_9001: string[]
  iso_14001: string[]
  iso_45001: string[]
  iso_27001: string[]
}

export interface UVDBIsoMappingResponse {
  description: string
  total_mappings: number
  mappings: UVDBIsoMappingRecord[]
}

/**
 * UVDB Achilles Audit API client.
 * Endpoints: /api/v1/uvdb/*
 */

export function createUvdbApi(api: AxiosInstance) {
  return {
  /**
   * Get UVDB dashboard summary.
   */
  getDashboard: () => api.get<UVDBDashboardResponse>('/api/v1/uvdb/dashboard'),

  /**
   * Get complete UVDB B2 protocol structure.
   */
  getProtocol: () =>
    api.get<{ sections: UVDBSectionRecord[]; total_questions: number }>('/api/v1/uvdb/protocol'),

  /**
   * List all UVDB sections.
   */
  listSections: () => api.get<UVDBSectionsResponse>('/api/v1/uvdb/sections'),

  /**
   * Get questions for a specific section.
   */
  getSectionQuestions: (sectionNumber: number) =>
    api.get<UVDBQuestion[]>(`/api/v1/uvdb/sections/${sectionNumber}/questions`),

  /**
   * List UVDB audits.
   */
  listAudits: (params?: {
    skip?: number
    limit?: number
    status?: string
    company_name?: string
    search?: string
    audit_type?: string
    date_from?: string
    date_to?: string
    min_score?: number
    max_score?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.skip !== undefined) sp.set('skip', String(params.skip))
    if (params?.limit !== undefined) sp.set('limit', String(params.limit))
    if (params?.status) sp.set('status', params.status)
    if (params?.company_name) sp.set('company_name', params.company_name)
    if (params?.search) sp.set('search', params.search)
    if (params?.audit_type) sp.set('audit_type', params.audit_type)
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    if (params?.min_score !== undefined) sp.set('min_score', String(params.min_score))
    if (params?.max_score !== undefined) sp.set('max_score', String(params.max_score))
    const query = sp.toString()
    return api.get<UVDBAuditsResponse>(`/api/v1/uvdb/audits${query ? `?${query}` : ''}`)
  },

  /**
   * Get a specific audit by ID.
   */
  getAudit: (auditId: number) => api.get<Record<string, unknown>>(`/api/v1/uvdb/audits/${auditId}`),

  /**
   * Get responses for an audit.
   */
  getAuditResponses: (auditId: number) =>
    api.get<UVDBAuditResponse[]>(`/api/v1/uvdb/audits/${auditId}/responses`),

  /**
   * Get ISO cross-mapping for UVDB sections.
   */
  getISOMapping: () => api.get<UVDBIsoMappingResponse>('/api/v1/uvdb/iso-mapping'),

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
    api.post<{ id: number; audit_reference: string; message: string }>('/api/v1/uvdb/audits', data),
}

// ============ User API ============

// User type for search results
// ============ Users API (extracted: usersClient.ts) ============
export type {
  UserSearchResult,
  UserDetail,
  RoleDetail,
  UserCreatePayload,
  UserUpdatePayload,
  RoleCreatePayload,
  RoleUpdatePayload,
} from './usersClient'
}

