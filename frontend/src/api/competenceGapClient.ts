/**
 * Competence gap closed-loop API — Assessor → Workforce.
 */
import api from './client'

export interface CompetenceGapAction {
  id: number
  tenant_id: number
  source_type: string
  source_id: number
  signal_type: string
  engineer_id: number | null
  requirement_id: number | null
  ticket_scheme: string | null
  capa_action_id: number | null
  status: string
  rationale: string | null
  confidence: number | null
  created_by_id: number
  resolved_at: string | null
  resolved_by_id: number | null
  created_at: string | null
  updated_at: string | null
  action_key: string | null
}

export interface CompetenceGapCapa {
  id: number
  reference_number: string
  title: string
  status: string
  priority: string
  owner_id: number | null
  due_date: string | null
  source_type: string
  source_id: number | null
  action_key: string
}

export interface GoldenThreadResponse {
  gap: CompetenceGapAction
  events: Array<{
    event: string
    at: string | null
    actor_id: number | null
    payload: Record<string, unknown>
  }>
  decision_log: Array<{
    event: string
    at: string | null
    actor_id: number | null
    payload: Record<string, unknown>
    confidence?: number | null
    auto_applied?: boolean
  }>
}

/** Minimal engineer shape for inbox link pickers (GET /api/v1/engineers/). */
export interface CompetenceGapPickerEngineer {
  id: number
  employee_number?: string
  job_title?: string
  is_active?: boolean
}

/** Minimal requirement shape for inbox link pickers. */
export interface CompetenceGapPickerRequirement {
  id: number
  name: string
}

const BASE = '/api/v1/workforce/competence-gaps'
const KNOWN_SOURCE_TYPES = new Set([
  'assessor_case',
  'external_audit_finding',
  'compliance_evidence_link',
])

export function competenceGapSourceLabelKey(sourceType: string): string {
  return KNOWN_SOURCE_TYPES.has(sourceType)
    ? `competenceGaps.source.${sourceType}`
    : 'competenceGaps.source.unknown'
}

export function engineerPickerLabel(engineer: CompetenceGapPickerEngineer): string {
  return engineer.employee_number || engineer.job_title || `Engineer #${engineer.id}`
}

export function requirementPickerLabel(requirement: CompetenceGapPickerRequirement): string {
  return requirement.name?.trim() || `Requirement #${requirement.id}`
}

export const competenceGapApi = {
  list: (params?: { status?: string }) =>
    api.get<CompetenceGapAction[]>(BASE, { params }),

  get: (id: number) => api.get<CompetenceGapAction>(`${BASE}/${id}`),

  fromSignal: (body: {
    source_type: string
    source_id: number
    signal_type?: string
    rationale?: string
    confidence?: number
  }) => api.post<CompetenceGapAction>(`${BASE}/from-signal`, body),

  link: (
    id: number,
    body: { engineer_id: number; requirement_id?: number; ticket_scheme?: string },
  ) => api.post<CompetenceGapAction>(`${BASE}/${id}/link`, body),

  createCapa: (
    id: number,
    body?: {
      owner_id?: number
      owner_email?: string
      due_date?: string
      priority?: string
    },
  ) =>
    api.post<{ gap: CompetenceGapAction; action: CompetenceGapCapa }>(
      `${BASE}/${id}/create-capa`,
      body ?? {},
    ),

  resolve: (
    id: number,
    body?: { notes?: string; dismiss?: boolean; close_capa?: boolean },
  ) => api.post<CompetenceGapAction>(`${BASE}/${id}/resolve`, body ?? {}),

  goldenThread: (id: number) =>
    api.get<GoldenThreadResponse>(`${BASE}/${id}/golden-thread`),

  /** Picker data for link step — existing workforce list endpoints. */
  listPickerEngineers: (params?: { page?: number; page_size?: number }) =>
    api.get<{ items: CompetenceGapPickerEngineer[]; total: number }>('/api/v1/engineers/', {
      params: { page: 1, page_size: 200, ...params },
    }),

  listPickerRequirements: (params?: { page?: number; page_size?: number }) =>
    api.get<{ items: CompetenceGapPickerRequirement[]; total: number }>(
      '/api/v1/competency-requirements/',
      { params: { page: 1, page_size: 200, ...params } },
    ),
}
