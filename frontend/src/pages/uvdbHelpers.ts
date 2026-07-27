import type { LucideIcon } from 'lucide-react'
import { BarChart3, Calendar, ClipboardList, Download, Link2 } from 'lucide-react'

export type UvdbSectionId = 'scores' | 'protocol' | 'audits' | 'mapping' | 'export'

export const UVDB_SECTION_IDS: UvdbSectionId[] = [
  'scores',
  'protocol',
  'audits',
  'mapping',
  'export',
]

export interface UvdbSectionDef {
  id: UvdbSectionId
  labelKey: string
  icon: LucideIcon
}

export const UVDB_SECTIONS: UvdbSectionDef[] = [
  { id: 'scores', labelKey: 'uvdb.shell.section.scores', icon: BarChart3 },
  { id: 'protocol', labelKey: 'uvdb.shell.section.protocol', icon: ClipboardList },
  { id: 'audits', labelKey: 'uvdb.shell.section.audits', icon: Calendar },
  { id: 'mapping', labelKey: 'uvdb.shell.section.mapping', icon: Link2 },
  { id: 'export', labelKey: 'uvdb.shell.section.export', icon: Download },
]

export function parseUvdbSection(
  value: string | null,
  options?: { auditRefHint?: boolean },
): UvdbSectionId {
  if (value && UVDB_SECTION_IDS.includes(value as UvdbSectionId)) {
    return value as UvdbSectionId
  }
  return options?.auditRefHint ? 'audits' : 'scores'
}

/** Score provenance for UVDB KPI honesty (PX-255 / PX-256). */
export type UvdbAverageProvenance = 'not_scored' | 'calculated' | 'imported' | 'mixed'

export type UvdbBoardAlignment = {
  protocolTotal: number
  protocolCompleted: number
  protocolAverage: number | null
  boardAchillesTotal: number
  countsDisagree: boolean
  averageProvenance: UvdbAverageProvenance
}

type ScoreSourceLike = 'calculated' | 'imported' | 'unknown' | string | null | undefined

/**
 * Compare UVDB specialist (protocol) KPIs with the Achilles slice on the Audits
 * board so operators never mistake a 3-row protocol table for the 12-row board.
 */
export function buildUvdbBoardAlignment(input: {
  protocolTotal: number
  protocolCompleted: number
  protocolAverage: number | null
  boardAchillesTotal: number
  scoredSources?: ScoreSourceLike[]
}): UvdbBoardAlignment {
  const sources = (input.scoredSources || []).filter(
    (source): source is string => typeof source === 'string' && source.length > 0,
  )
  const hasImported = sources.some((source) => source === 'imported')
  const hasCalculated = sources.some((source) => source === 'calculated')
  let averageProvenance: UvdbAverageProvenance = 'not_scored'
  if (input.protocolAverage != null) {
    if (hasImported && hasCalculated) averageProvenance = 'mixed'
    else if (hasImported) averageProvenance = 'imported'
    else if (hasCalculated) averageProvenance = 'calculated'
    else averageProvenance = 'imported'
  }

  return {
    protocolTotal: input.protocolTotal,
    protocolCompleted: input.protocolCompleted,
    protocolAverage: input.protocolAverage,
    boardAchillesTotal: input.boardAchillesTotal,
    countsDisagree: input.protocolTotal !== input.boardAchillesTotal,
    averageProvenance,
  }
}

export function formatUvdbAverageKpi(alignment: UvdbBoardAlignment): {
  value: string
  caption: string
} {
  if (alignment.protocolAverage == null || alignment.averageProvenance === 'not_scored') {
    return {
      value: 'Not scored',
      caption: 'No completed protocol score recorded',
    }
  }

  const value = `${alignment.protocolAverage}%`
  if (alignment.averageProvenance === 'imported') {
    return {
      value,
      caption: 'Imported report average — not verified against loaded protocol questions',
    }
  }
  if (alignment.averageProvenance === 'mixed') {
    return {
      value,
      caption: 'Mix of imported and in-app scores — not a single verified qualification figure',
    }
  }
  return {
    value,
    caption: 'Calculated in-app from UVDB protocol responses',
  }
}

/** PX-255 — pending-empty protocol shells must not display a qualification %. */
export type UvdbContentStatus = 'loaded' | 'pending_protocol_pdf'

export type UvdbSectionScoreLike = {
  score?: number | null
  max_score?: number | null
  percentage?: number | null
  score_source?: string | null
  assessed?: boolean
  excluded_from_qualification?: boolean
  exclusion_reason?: string | null
}

/**
 * Display gate for protocol section cards: pending / excluded sections render
 * as not scored (no green bar), never as a fabricated compliance %.
 *
 * Generic so callers keep their concrete `score_source` union (e.g. ScoreSource)
 * instead of widening to `string`.
 */
export function gateUvdbSectionScoreForDisplay<T extends UvdbSectionScoreLike>(
  score: T | null | undefined,
  contentStatus: UvdbContentStatus | undefined,
): T | null {
  if (!score) return null
  const pending = contentStatus === 'pending_protocol_pdf'
  const excluded =
    score.excluded_from_qualification === true ||
    score.assessed === false ||
    pending
  if (!excluded) return score
  return {
    ...score,
    score: null,
    percentage: null,
    assessed: false,
    excluded_from_qualification: true,
    exclusion_reason: score.exclusion_reason || 'pending_protocol_pdf',
  }
}

export function uvdbPendingScoreExclusionCopy(reason?: string | null): string {
  if (reason === 'empty_section') {
    return 'This section has no loaded questions, so it is excluded from the qualification score.'
  }
  return (
    'Questions pending protocol PDF — excluded from the qualification score so an ' +
    'imported figure cannot count as assessed.'
  )
}
