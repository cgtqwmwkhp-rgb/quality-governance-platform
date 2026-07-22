import axios from 'axios'

import { buildEvidenceResponseJson } from './auditExecutionPhotoEvidence'

type ResponseJsonInput = {
  response: unknown
  evidenceAssetIds?: number[]
  entityLabel?: string
}

const ENTITY_SELECT_QUESTION_TYPES = new Set(['user_select', 'location_select', 'customer_select'])

/** Merge evidence spine ids with checklist/radio selected values for response_json. */
export function mergeAuditResponseJson(
  resp: ResponseJsonInput,
  questionType?: string,
): Record<string, unknown> | undefined {
  const json: Record<string, unknown> = {}
  const assetIds = resp.evidenceAssetIds?.filter((id) => id > 0) ?? []
  if (assetIds.length > 0) {
    Object.assign(json, buildEvidenceResponseJson(assetIds))
  }
  if (questionType === 'checklist' && Array.isArray(resp.response) && resp.response.length > 0) {
    json.selected = resp.response
  } else if (
    questionType === 'multi_choice' &&
    typeof resp.response === 'string' &&
    resp.response.trim()
  ) {
    json.selected = resp.response
  } else if (
    questionType &&
    ENTITY_SELECT_QUESTION_TYPES.has(questionType) &&
    resp.entityLabel?.trim() &&
    typeof resp.response === 'string' &&
    resp.response.trim()
  ) {
    // Best-effort label snapshot so the run summary can show a name instead
    // of a bare id — scoring only relies on response_value being present.
    json.entity_label = resp.entityLabel.trim()
  }
  return Object.keys(json).length > 0 ? json : undefined
}

function readMissingIds(details: unknown): number[] {
  if (!details || typeof details !== 'object') return []
  const raw = (details as { missing_question_ids?: unknown }).missing_question_ids
  if (!Array.isArray(raw)) return []
  return raw.map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0)
}

/** Parse PR-A complete_run 400 envelope: error.details.missing_question_ids. */
export function parseMissingQuestionIdsFromError(error: unknown): number[] {
  if (!axios.isAxiosError(error)) return []
  const data = error.response?.data as Record<string, unknown> | undefined
  if (!data) return []

  const nestedError = data.error
  if (nestedError && typeof nestedError === 'object' && nestedError !== null) {
    const fromNested = readMissingIds((nestedError as { details?: unknown }).details)
    if (fromNested.length > 0) return fromNested
  }

  const fromRoot = readMissingIds(data.details)
  if (fromRoot.length > 0) return fromRoot

  const detail = data.detail
  if (detail && typeof detail === 'object' && detail !== null) {
    const fromDetail = readMissingIds((detail as { details?: unknown }).details)
    if (fromDetail.length > 0) return fromDetail
  }

  return []
}

export function formatMissingQuestionsMessage(missingCount: number): string {
  if (missingCount === 1) {
    return 'Complete the highlighted required question before submitting this audit.'
  }
  return `${missingCount} required questions still need answers. Jumped to the first missing question.`
}

export type SavePayloadQuestion = {
  type: string
  weight: number
  maxScore?: number
  maxValue?: number
  positiveAnswer?: 'yes' | 'no'
  options?: { value: string; label: string; score?: number }[]
}

type SavePayloadResponse = {
  response: unknown
  notes?: string
  evidenceAssetIds?: number[]
  entityLabel?: string
}

export type AuditResponseSavePayload = {
  response_value: string | null
  notes: string | null
  score: number | null
  max_score: number | null
  is_na: boolean
  response_json?: Record<string, unknown> | null
}

function serializeResponseValue(response: unknown): string | undefined {
  if (response === null || response === undefined) return undefined
  if (typeof response === 'number') return String(response)
  if (Array.isArray(response)) return JSON.stringify(response)
  return String(response)
}

/** Build create/update payload with is_na + merged response_json for PR-A gate. */
export function buildAuditResponseSavePayload(
  resp: SavePayloadResponse,
  question: SavePayloadQuestion | undefined,
  scorePayloadForQuestion: (
    question: SavePayloadQuestion,
    response: SavePayloadResponse,
  ) => { score: number | null; max_score: number | null },
): AuditResponseSavePayload {
  const isNa = resp.response === 'na'
  const scored = question
    ? scorePayloadForQuestion(question, resp)
    : { score: null, max_score: null }
  const responseJson = mergeAuditResponseJson(
    { response: resp.response, evidenceAssetIds: resp.evidenceAssetIds, entityLabel: resp.entityLabel },
    question?.type,
  )

  return {
    response_value: isNa ? 'na' : (serializeResponseValue(resp.response) ?? null),
    notes: resp.notes || null,
    score: scored.score,
    max_score: scored.max_score,
    is_na: isNa,
    response_json: responseJson ?? null,
  }
}

export function responseRowIsEmpty(resp: SavePayloadResponse): boolean {
  if (resp.response === 'na') return false
  const hasEvidence = (resp.evidenceAssetIds?.length ?? 0) > 0
  const hasNotes = Boolean(resp.notes?.trim())
  if (hasEvidence || hasNotes) return false
  if (resp.response === null || resp.response === undefined || resp.response === '') return true
  if (Array.isArray(resp.response) && resp.response.length === 0) return true
  return false
}
