/** MAP Assist suggest + confirm — must use shared API base (never SWA-relative fetch). */

import type { AxiosError } from 'axios'
import api from '../api/client'
import type { MapW3StandardLink } from './mapW3StaleRescoreHonesty'

export interface BuilderSuggestQuestionInput {
  question_id: string
  question_text: string
  description?: string
}

export interface BuilderStandardsCoverage {
  template_id?: number
  total_questions: number
  questions_with_accepted_links: number
  accepted_multi_scheme_links: number
  coverage_percent: number
  by_scheme: Record<string, number>
  assist_map_live: boolean
  library_version?: string
}

function parseApiError(err: unknown): string {
  const ax = err as AxiosError<{ detail?: unknown; error?: { message?: string } }>
  const status = ax.response?.status
  const data = ax.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (data?.detail != null) {
    try {
      return JSON.stringify(data.detail)
    } catch {
      /* fall through */
    }
  }
  if (typeof data?.error?.message === 'string') return data.error.message
  if (status === 405) {
    return 'Assist Map API unreachable from this host (HTTP 405). Requests must use the App Service API base, not the Static Web App origin.'
  }
  if (status) return `HTTP ${status}`
  return ax.message || 'Assist Map request failed'
}

function normalizeLink(row: Record<string, unknown>, fallbackQuestionId?: string | number): MapW3StandardLink {
  return {
    id: String(row.id),
    questionId: String(row.questionId ?? row.question_id ?? fallbackQuestionId ?? ''),
    scheme: String(row.scheme),
    refId: String(row.refId ?? row.ref_id),
    label: String(row.label ?? row.refId ?? row.ref_id ?? ''),
    confidence: Number(row.confidence ?? 0),
    status: (row.status as MapW3StandardLink['status']) ?? 'suggested',
    sourceFingerprint: String(row.sourceFingerprint ?? row.source_fingerprint ?? ''),
    libraryVersion: String(row.libraryVersion ?? row.library_version ?? 'builder-map-v1'),
  }
}

/**
 * Build IMS Standards deep-link for an Assist ISO ref like `9001-7.2` or `7.2`.
 * Opens /standards with standard code + clause search for inspection prep.
 */
export function standardsHrefForIsoRef(refId: string): string {
  const raw = (refId || '').trim()
  const sp = new URLSearchParams()
  const prefixed = raw.match(/^(9001|14001|45001|27001|22000)[-:](.+)$/i)
  if (prefixed) {
    const codeNum = prefixed[1]
    const clause = prefixed[2].trim()
    sp.set('code', `ISO${codeNum}`)
    sp.set('clause', clause)
    return `/standards?${sp.toString()}`
  }
  if (raw) sp.set('clause', raw)
  return `/standards?${sp.toString()}`
}

export async function suggestStandardLinks(
  questions: BuilderSuggestQuestionInput[],
  schemes: string[] = ['ISO', 'Planet Mark', 'UVDB'],
): Promise<MapW3StandardLink[]> {
  try {
    const { data } = await api.post<{
      suggestions?: Array<Record<string, unknown>>
      library_version?: string
    }>('/api/v1/ai-templates/suggest-standard-links', { questions, schemes })
    const suggestions = data.suggestions ?? []
    return suggestions.map((row) =>
      normalizeLink({
        ...row,
        libraryVersion: row.libraryVersion ?? row.library_version ?? data.library_version,
        status: 'suggested',
      }),
    )
  } catch (err) {
    throw new Error(parseApiError(err))
  }
}

export async function decideStandardLink(
  questionId: number,
  decision: 'accept' | 'edit' | 'reject',
  link: MapW3StandardLink,
  opts?: { editedRefId?: string; editedLabel?: string; rationale?: string },
): Promise<{ link: MapW3StandardLink; links: MapW3StandardLink[] }> {
  try {
    const { data } = await api.post<{
      link?: Record<string, unknown>
      links?: Array<Record<string, unknown>>
    }>(`/api/v1/ai-templates/questions/${questionId}/standard-links/decide`, {
      decision,
      link: {
        id: link.id,
        scheme: link.scheme,
        refId: link.refId,
        label: link.label,
        confidence: link.confidence,
        status: link.status,
        sourceFingerprint: link.sourceFingerprint,
        libraryVersion: link.libraryVersion,
      },
      edited_ref_id: opts?.editedRefId,
      edited_label: opts?.editedLabel,
      rationale: opts?.rationale,
    })
    return {
      link: normalizeLink(data.link ?? {}, questionId),
      links: Array.isArray(data.links) ? data.links.map((row) => normalizeLink(row, questionId)) : [],
    }
  } catch (err) {
    throw new Error(parseApiError(err))
  }
}

export async function fetchTemplateStandardsCoverage(
  templateId: number,
): Promise<BuilderStandardsCoverage> {
  try {
    const { data } = await api.get<BuilderStandardsCoverage>(
      `/api/v1/ai-templates/templates/${templateId}/standards-coverage`,
    )
    return data
  } catch (err) {
    throw new Error(parseApiError(err))
  }
}
