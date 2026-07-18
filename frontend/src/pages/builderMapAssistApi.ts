/** Thin fetch helpers for MAP Assist suggest + confirm persist (ai-templates). */

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

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  try {
    const token = localStorage.getItem('access_token') || localStorage.getItem('token')
    if (token) headers.Authorization = `Bearer ${token}`
  } catch {
    // ignore storage access errors in tests / SSR
  }
  return headers
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') return body.detail
    return JSON.stringify(body?.detail ?? body)
  } catch {
    return response.statusText || `HTTP ${response.status}`
  }
}

export async function suggestStandardLinks(
  questions: BuilderSuggestQuestionInput[],
  schemes: string[] = ['ISO', 'Planet Mark', 'UVDB'],
): Promise<MapW3StandardLink[]> {
  const response = await fetch('/api/v1/ai-templates/suggest-standard-links', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ questions, schemes }),
  })
  if (!response.ok) {
    throw new Error(await parseError(response))
  }
  const data = await response.json()
  const suggestions = (data.suggestions ?? []) as Array<Record<string, unknown>>
  return suggestions.map((row) => ({
    id: String(row.id),
    questionId: String(row.questionId ?? row.question_id),
    scheme: String(row.scheme),
    refId: String(row.refId ?? row.ref_id),
    label: String(row.label ?? row.refId ?? row.ref_id),
    confidence: Number(row.confidence ?? 0),
    status: 'suggested' as const,
    sourceFingerprint: String(row.sourceFingerprint ?? ''),
    libraryVersion: String(row.libraryVersion ?? data.library_version ?? 'builder-map-v1'),
  }))
}

export async function decideStandardLink(
  questionId: number,
  decision: 'accept' | 'edit' | 'reject',
  link: MapW3StandardLink,
  opts?: { editedRefId?: string; editedLabel?: string; rationale?: string },
): Promise<{ link: MapW3StandardLink; links: MapW3StandardLink[] }> {
  const response = await fetch(`/api/v1/ai-templates/questions/${questionId}/standard-links/decide`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
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
    }),
  })
  if (!response.ok) {
    throw new Error(await parseError(response))
  }
  const data = await response.json()
  const normalize = (row: Record<string, unknown>): MapW3StandardLink => ({
    id: String(row.id),
    questionId: String(row.questionId ?? questionId),
    scheme: String(row.scheme),
    refId: String(row.refId ?? row.ref_id),
    label: String(row.label ?? ''),
    confidence: Number(row.confidence ?? 0),
    status: (row.status as MapW3StandardLink['status']) ?? 'accepted',
    sourceFingerprint: String(row.sourceFingerprint ?? ''),
    libraryVersion: String(row.libraryVersion ?? 'builder-map-v1'),
  })
  return {
    link: normalize(data.link ?? {}),
    links: Array.isArray(data.links) ? data.links.map(normalize) : [],
  }
}

export async function fetchTemplateStandardsCoverage(
  templateId: number,
): Promise<BuilderStandardsCoverage> {
  const response = await fetch(
    `/api/v1/ai-templates/templates/${templateId}/standards-coverage`,
    { headers: authHeaders() },
  )
  if (!response.ok) {
    throw new Error(await parseError(response))
  }
  return response.json()
}
