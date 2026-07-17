/** MAP-W2 — Assist / multi-scheme standards mapping honesty for Inspection + Competency builders. */

export const MAP_W2_SCHEME_CHIPS = ['ISO', 'Planet Mark', 'UVDB'] as const

export type MapW2SchemeChip = (typeof MAP_W2_SCHEME_CHIPS)[number]

export type MapW2SchemeStatus = 'manual_iso' | 'awaiting_assist'

export interface MapW2QuestionLike {
  isoClause?: string | null
}

export interface MapW2CoverageStats {
  totalQuestions: number
  withIsoClause: number
  /** Manual free-text ISO clause coverage only (0–100). */
  isoCoveragePercent: number
  /** Accepted multi-scheme Assist links — always 0 until MAP-W3 / confirm loop lands. */
  acceptedMultiSchemeLinks: number
  /** True only when Assist Map mode can accept multi-scheme chips. */
  assistMapLive: boolean
}

export function hasIsoClauseText(value: string | null | undefined): boolean {
  return Boolean(value && value.trim().length > 0)
}

/** Coverage from Advanced Settings free-text ISO Clause — not Assist accept chips. */
export function computeIsoClauseCoverage(questions: MapW2QuestionLike[]): MapW2CoverageStats {
  const totalQuestions = questions.length
  const withIsoClause = questions.filter((q) => hasIsoClauseText(q.isoClause)).length
  const isoCoveragePercent =
    totalQuestions === 0 ? 0 : Math.round((withIsoClause / totalQuestions) * 100)
  return {
    totalQuestions,
    withIsoClause,
    isoCoveragePercent,
    acceptedMultiSchemeLinks: 0,
    assistMapLive: false,
  }
}

export function schemeChipStatus(scheme: MapW2SchemeChip, stats: MapW2CoverageStats): MapW2SchemeStatus {
  if (scheme === 'ISO' && stats.withIsoClause > 0) return 'manual_iso'
  return 'awaiting_assist'
}

export function isCompetencyAssessmentSurface(surface: 'inspection' | 'competency'): boolean {
  return surface === 'competency'
}
