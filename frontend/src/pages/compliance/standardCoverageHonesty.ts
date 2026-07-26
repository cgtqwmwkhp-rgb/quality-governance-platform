/** Coverage provenance for Compliance Evidence standard tiles (PX-234 / PX-253 / PX-254). */

export type StandardCoverageState =
  | {
      kind: 'coverage'
      percent: number
      covered: number
      partial: number
      gaps: number
      total: number
    }
  | { kind: 'unavailable' }
  | { kind: 'degraded'; message: string }
  | { kind: 'not_adopted'; clauseTotal: number; clausesWithEvidence: number }

export function standardCoverageState(input: {
  coverageUnavailable: boolean
  canonicalDataDegraded: boolean
  canonicalDataMessage: string | null
  hasCanonicalStandard: boolean
  stats: { total: number; covered: number; partial: number; gaps: number }
}): StandardCoverageState {
  if (input.coverageUnavailable) return { kind: 'unavailable' }
  // Must precede not_adopted: when canonical enrichment fails, has_canonical_standard
  // is false for every standard — that is a failed lookup, not a tenant decision (PX-234).
  if (input.canonicalDataDegraded) {
    return {
      kind: 'degraded',
      message: input.canonicalDataMessage ?? 'Canonical standard lookup failed',
    }
  }
  if (!input.hasCanonicalStandard) {
    return {
      kind: 'not_adopted',
      clauseTotal: input.stats.total,
      clausesWithEvidence: input.stats.covered + input.stats.partial,
    }
  }
  const total = input.stats.total
  const percent =
    total > 0
      ? Math.round(((input.stats.covered + input.stats.partial * 0.5) / total) * 100)
      : 0
  return {
    kind: 'coverage',
    percent,
    covered: input.stats.covered,
    partial: input.stats.partial,
    gaps: input.stats.gaps,
    total,
  }
}

export function standardProvenanceLabel(state: StandardCoverageState): string {
  switch (state.kind) {
    case 'coverage':
      return 'Adopted standard'
    case 'unavailable':
      return 'Coverage unavailable'
    case 'degraded':
      return 'canonical enrichment degraded'
    case 'not_adopted':
      return 'Not adopted in this tenant — built-in ISO clause list'
  }
}

export function clauseDenominatorNote(
  breakdown: Record<string, number> | undefined,
): string | null {
  if (!breakdown) return null
  const management = breakdown.management_clauses
  const annex = breakdown.annex_a_controls
  if (typeof management !== 'number' || typeof annex !== 'number') return null
  const total = management + annex
  return (
    `${total} clauses assessed: ${management} ISMS management clauses (4–10) + ` +
    `${annex} Annex A controls. The Statement of Applicability assesses the ` +
    `${annex} Annex A controls only.`
  )
}
