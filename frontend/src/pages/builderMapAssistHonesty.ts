/** MAP-W2 / MAP-01..04 — Assist multi-scheme standards mapping + confirm-loop honesty. */

import type { MapW3LinkStatus, MapW3StandardLink } from './mapW3StaleRescoreHonesty'

export const MAP_W2_SCHEME_CHIPS = ['ISO', 'Planet Mark', 'UVDB'] as const

export type MapW2SchemeChip = (typeof MAP_W2_SCHEME_CHIPS)[number]

export type MapW2SchemeStatus = 'manual_iso' | 'awaiting_assist' | 'accepted' | 'suggested'

export interface MapW2QuestionLike {
  id?: string
  isoClause?: string | null
  standardLinks?: MapW3StandardLink[] | null
}

export interface MapW2CoverageStats {
  totalQuestions: number
  withIsoClause: number
  /** Manual free-text ISO clause coverage only (0–100). */
  isoCoveragePercent: number
  /** Questions with ≥1 accepted multi-scheme Assist link. */
  questionsWithAcceptedLinks: number
  /** Accepted multi-scheme Assist links (live confirm loop). */
  acceptedMultiSchemeLinks: number
  /** Multi-scheme coverage % (questions with ≥1 accepted link). */
  multiSchemeCoveragePercent: number
  bySchemeAccepted: Record<MapW2SchemeChip, number>
  /** True when Assist Map confirm loop is wired and live. */
  assistMapLive: boolean
}

export type MapConfirmDecision = 'accept' | 'edit' | 'reject'

export function hasIsoClauseText(value: string | null | undefined): boolean {
  return Boolean(value && value.trim().length > 0)
}

export function flattenQuestionLinks(questions: MapW2QuestionLike[]): MapW3StandardLink[] {
  return questions.flatMap((q) => q.standardLinks ?? [])
}

/** Coverage from Advanced Settings free-text ISO Clause + accepted multi-scheme links. */
export function computeIsoClauseCoverage(questions: MapW2QuestionLike[]): MapW2CoverageStats {
  const totalQuestions = questions.length
  const withIsoClause = questions.filter((q) => hasIsoClauseText(q.isoClause)).length
  const isoCoveragePercent =
    totalQuestions === 0 ? 0 : Math.round((withIsoClause / totalQuestions) * 100)

  const links = flattenQuestionLinks(questions)
  const accepted = links.filter((l) => l.status === 'accepted')
  const questionsWithAcceptedLinks = questions.filter((q) =>
    (q.standardLinks ?? []).some((l) => l.status === 'accepted'),
  ).length
  const multiSchemeCoveragePercent =
    totalQuestions === 0 ? 0 : Math.round((questionsWithAcceptedLinks / totalQuestions) * 100)

  const bySchemeAccepted: Record<MapW2SchemeChip, number> = {
    ISO: 0,
    'Planet Mark': 0,
    UVDB: 0,
  }
  for (const link of accepted) {
    const scheme = link.scheme as MapW2SchemeChip
    if (scheme in bySchemeAccepted) {
      bySchemeAccepted[scheme] += 1
    }
  }

  return {
    totalQuestions,
    withIsoClause,
    isoCoveragePercent,
    questionsWithAcceptedLinks,
    acceptedMultiSchemeLinks: accepted.length,
    multiSchemeCoveragePercent,
    bySchemeAccepted,
    assistMapLive: true,
  }
}

export function schemeChipStatus(scheme: MapW2SchemeChip, stats: MapW2CoverageStats): MapW2SchemeStatus {
  if (stats.bySchemeAccepted[scheme] > 0) return 'accepted'
  if (scheme === 'ISO' && stats.withIsoClause > 0) return 'manual_iso'
  return 'awaiting_assist'
}

export function isCompetencyAssessmentSurface(surface: 'inspection' | 'competency'): boolean {
  return surface === 'competency'
}

/** Apply Accept / Edit / Reject in local confirm-loop state (MAP-04). */
export function applyConfirmDecision(
  links: MapW3StandardLink[],
  linkId: string,
  decision: MapConfirmDecision,
  edits?: { refId?: string; label?: string },
): MapW3StandardLink[] {
  const nextStatus: MapW3LinkStatus = decision === 'reject' ? 'rejected' : 'accepted'
  return links.map((link) => {
    if (link.id !== linkId) return link
    return {
      ...link,
      status: nextStatus,
      refId: edits?.refId?.trim() || link.refId,
      label: edits?.label?.trim() || link.label,
    }
  })
}

/** Merge Assist suggestions into existing links without clobbering accepted/rejected. */
export function mergeSuggestedLinks(
  existing: MapW3StandardLink[],
  suggestions: MapW3StandardLink[],
): MapW3StandardLink[] {
  const keyed = new Map<string, MapW3StandardLink>()
  for (const link of existing) {
    keyed.set(`${link.questionId}|${link.scheme}|${link.refId}`, link)
  }
  for (const suggestion of suggestions) {
    const key = `${suggestion.questionId}|${suggestion.scheme}|${suggestion.refId}`
    const prior = keyed.get(key)
    if (prior && (prior.status === 'accepted' || prior.status === 'rejected')) {
      continue
    }
    keyed.set(key, { ...suggestion, status: 'suggested' })
  }
  return Array.from(keyed.values())
}

export function linksForQuestion(
  links: MapW3StandardLink[],
  questionId: string,
): MapW3StandardLink[] {
  return links.filter((l) => l.questionId === questionId)
}

export function primaryAcceptedIsoClause(links: MapW3StandardLink[]): string | undefined {
  const iso = links.find((l) => l.scheme === 'ISO' && l.status === 'accepted')
  return iso?.refId
}
