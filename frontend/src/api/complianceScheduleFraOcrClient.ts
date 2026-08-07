/**
 * Compliance Schedule FRA / PAS79 OCR ingest API client (Wave 3).
 */
import type { AxiosInstance } from 'axios'
import type { ComplianceRequirement } from './complianceScheduleClient'

export type FraFieldConfidence = 'high' | 'medium' | 'none'
export type FraRiskVocabulary = 'pas79' | 'lmh'
export type FraActionPriority = 'high' | 'medium' | 'low'
export type FraOcrDraftStatus = 'pending' | 'confirmed' | 'discarded'
export type FraOcrFilingStatus = 'not_filed' | 'filed' | 'filing_failed'

export interface FraExtractedField {
  value?: string | null
  confidence: FraFieldConfidence
  evidence_snippet?: string | null
}

export interface FraProposedAction {
  index: number
  source_ref?: string | null
  text: string
  priority_raw?: string | null
  priority_normalised?: FraActionPriority | null
  target_date?: string | null
  target_date_raw?: string | null
  confidence: FraFieldConfidence
  needs_review: boolean
}

export interface FraProposedFields {
  assessment_date: FraExtractedField
  next_review_date: FraExtractedField
  review_interval_months: FraExtractedField
  assessor_name: FraExtractedField
  assessor_organisation: FraExtractedField
  premises_name: FraExtractedField
  pas79_reference: FraExtractedField
  overall_risk_rating: FraExtractedField
  risk_vocabulary?: FraRiskVocabulary | null
}

export interface FraOcrAppliedSummary {
  requirement_id: number
  next_due_date_before: string
  next_due_date_after: string
  actions_recorded: number
  actions_created: number
  changed_fields: string[]
  warnings: string[]
}

export interface FraOcrDraftResponse {
  id: number
  external_id: string
  tenant_id: number
  requirement_id: number
  purpose: 'fra_pas79'
  status: FraOcrDraftStatus
  source_filename?: string | null
  source_size_bytes?: number | null
  source_checksum_sha256: string
  extraction_method?: string | null
  ocr_provider_status?: string | null
  page_count?: number | null
  proposed: FraProposedFields
  proposed_actions: FraProposedAction[]
  warnings: string[]
  confirmed_at?: string | null
  confirmed_by_id?: number | null
  applied?: FraOcrAppliedSummary | null
  library_document_id?: number | null
  filing_status: FraOcrFilingStatus
  filing_error?: string | null
  created_at: string
  updated_at?: string | null
}

export interface FraOcrDraftListResponse {
  items: FraOcrDraftResponse[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface FraOcrConfirmedActionPayload {
  index: number
  text: string
  priority_normalised?: FraActionPriority | null
  target_date?: string | null
}

export interface FraOcrDraftConfirmPayload {
  next_due_date: string
  acknowledged_warnings?: boolean
  actions?: FraOcrConfirmedActionPayload[]
  note?: string | null
}

export interface FraOcrConfirmResponse {
  draft: FraOcrDraftResponse
  requirement: ComplianceRequirement
  applied: FraOcrAppliedSummary
}

export interface FraOcrFilePayload {
  category_id: number
  title?: string
}

export interface FraOcrFilingResponse {
  draft: FraOcrDraftResponse
  library_document_id: number
  pel_doc_ref?: string | null
  duplicate_warning: boolean
  duplicate_warning_detail?: Array<Record<string, unknown>> | null
}

export interface FraOcrDiscardPayload {
  reason?: string | null
}

export function createComplianceScheduleFraOcrApi(api: AxiosInstance) {
  const base = '/api/v1/compliance-schedule'

  return {
    createDraft: (requirementId: number, file: File) => {
      const body = new FormData()
      body.append('file', file)
      return api.post<FraOcrDraftResponse>(
        `${base}/requirements/${requirementId}/fra-ocr/drafts`,
        body,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
    },

    listDrafts: (
      requirementId: number,
      params?: { page?: number; page_size?: number; status?: FraOcrDraftStatus },
    ) =>
      api.get<FraOcrDraftListResponse>(
        `${base}/requirements/${requirementId}/fra-ocr/drafts`,
        { params },
      ),

    getDraft: (draftId: number) =>
      api.get<FraOcrDraftResponse>(`${base}/fra-ocr/drafts/${draftId}`),

    confirmDraft: (draftId: number, data: FraOcrDraftConfirmPayload) =>
      api.post<FraOcrConfirmResponse>(`${base}/fra-ocr/drafts/${draftId}/confirm`, data),

    fileDraft: (draftId: number, data: FraOcrFilePayload) =>
      api.post<FraOcrFilingResponse>(`${base}/fra-ocr/drafts/${draftId}/file`, data),

    discardDraft: (draftId: number, data?: FraOcrDiscardPayload) =>
      api.post<FraOcrDraftResponse>(`${base}/fra-ocr/drafts/${draftId}/discard`, data ?? {}),
  }
}

export type ComplianceScheduleFraOcrApi = ReturnType<typeof createComplianceScheduleFraOcrApi>
