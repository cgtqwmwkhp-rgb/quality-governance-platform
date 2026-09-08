/**
 * Detail-lane API helpers (avoid colliding with InvList investigationsClient edits).
 *
 * INV-C10 RCA calls live here, not on the shell `investigationsApi` factory:
 * InvestigationDetail is already a lazy route chunk, and two extra methods on
 * the shell client were enough to push index-*.js over the 212 kB gzip ceiling.
 */
import api from '../../api/client'

export interface InvestigationRcaWhy {
  level: number
  why?: string
  answer: string
  evidence: string
}

export interface InvestigationRcaResponse {
  id: number | null
  investigation_id: number
  problem_statement: string
  whys: InvestigationRcaWhy[]
  root_cause: string
  contributing_factors: string
}

export interface InvestigationRcaUpsert {
  problem_statement: string
  whys: Array<{
    level: number
    answer: string
    evidence?: string
    why?: string
  }>
  root_cause: string
  /**
   * INV-C12: deliberately not sent by this page any more.
   *
   * The ICAM factor list below is the author of that text; the server derives
   * it from the factors on every factor mutation. Sending a copy from here
   * would be a second writer for one field, which is the PX-168 shape. Omitted
   * means "leave it alone", which is exactly what this page wants.
   */
  contributing_factors?: string
}

/** ICAM contributing factor (INV-C12). `category` and `depth` are server enums. */
export interface InvestigationFactor {
  id: number
  investigation_id: number
  category: string
  cause: string
  sub_causes: string[]
  depth: string | null
}

export interface InvestigationFactorListResponse {
  items: InvestigationFactor[]
  total: number
  investigation_id: number
  diagram_id: number | null
  contributing_factors_text: string
  unmapped_categories: string[]
  unreadable_total: number
}

export interface InvestigationFactorInput {
  category: string
  cause: string
  sub_causes?: string[]
  depth?: string | null
}

export function getRca(id: number) {
  return api.get<InvestigationRcaResponse>(`/api/v1/investigations/${id}/rca`)
}

export function saveRca(id: number, body: InvestigationRcaUpsert) {
  return api.put<InvestigationRcaResponse>(`/api/v1/investigations/${id}/rca`, body)
}

export function createCapaFromWhy(
  id: number,
  body: {
    why_level: number
    title?: string
    description?: string
    five_whys_id?: number
    priority?: string
    due_date?: string
  },
) {
  return api.post<{
    id: number
    reference_number: string
    title: string
    five_whys_id?: number | null
    why_level?: number | null
  }>(`/api/v1/investigations/${id}/rca/capa`, body)
}

export function listFactors(id: number) {
  return api.get<InvestigationFactorListResponse>(`/api/v1/investigations/${id}/factors`)
}

export function createFactor(id: number, body: InvestigationFactorInput) {
  return api.post<InvestigationFactorListResponse>(`/api/v1/investigations/${id}/factors`, body)
}

export function updateFactor(
  id: number,
  factorId: number,
  body: Partial<InvestigationFactorInput>,
) {
  return api.patch<InvestigationFactorListResponse>(
    `/api/v1/investigations/${id}/factors/${factorId}`,
    body,
  )
}

export function deleteFactor(id: number, factorId: number) {
  return api.delete<InvestigationFactorListResponse>(
    `/api/v1/investigations/${id}/factors/${factorId}`,
  )
}

export type CustomerPackVisibilityMeta = {
  omit_requested?: boolean
  omit_approved?: boolean
  omit_reason?: string | null
  omit_requested_by?: number | null
  omit_approved_by?: number | null
  omit_approved_at?: string | null
}

export async function addManualTimelineEntry(investigationId: number, content: string) {
  return api.post(`/api/v1/investigations/${investigationId}/timeline`, { content })
}

export async function requestCustomerPackOmit(
  investigationId: number,
  sectionId: string,
  omitRequested: boolean,
  reason?: string,
) {
  return api.post(`/api/v1/investigations/${investigationId}/customer-pack-omit`, {
    section_id: sectionId,
    omit_requested: omitRequested,
    reason,
  })
}

export async function approveCustomerPackOmit(
  investigationId: number,
  sectionId: string,
  reason?: string,
) {
  return api.post(`/api/v1/investigations/${investigationId}/customer-pack-omit/approve`, {
    section_id: sectionId,
    reason,
  })
}

export async function updateEvidenceVisibility(assetId: number, visibility: string) {
  return api.patch(`/api/v1/evidence-assets/${assetId}`, { visibility })
}

/**
 * Fetch a generated customer pack as PDF bytes (PX-143).
 *
 * The server renders the stored pack payload, so this cannot return content the pack's
 * redaction rules removed.
 */
export async function fetchCustomerPackPdf(investigationId: number, packId: number): Promise<Blob> {
  const response = await api.get<Blob>(
    `/api/v1/investigations/${investigationId}/packs/${packId}/pdf`,
    { responseType: 'blob' },
  )
  return response.data
}

export function readCustomerPackVisibility(
  data: Record<string, unknown> | null | undefined,
): Record<string, CustomerPackVisibilityMeta> {
  const raw = data?.customer_pack_visibility
  if (!raw || typeof raw !== 'object') return {}
  return raw as Record<string, CustomerPackVisibilityMeta>
}
