import { describe, expect, it } from 'vitest'
import {
  clauseDenominatorNote,
  standardCoverageState,
  standardProvenanceLabel,
} from '../standardCoverageHonesty'

describe('standardCoverageHonesty (PX-234 / PX-253 / PX-254)', () => {
  const stats = { total: 117, covered: 10, partial: 6, gaps: 101 }

  it('prefers degraded over not_adopted when canonical lookup fails', () => {
    const state = standardCoverageState({
      coverageUnavailable: false,
      canonicalDataDegraded: true,
      canonicalDataMessage: 'lookup failed',
      hasCanonicalStandard: false,
      stats,
    })
    expect(state.kind).toBe('degraded')
    expect(standardProvenanceLabel(state)).toMatch(/degraded/i)
  })

  it('withholds percentage when standard is not adopted', () => {
    const state = standardCoverageState({
      coverageUnavailable: false,
      canonicalDataDegraded: false,
      canonicalDataMessage: null,
      hasCanonicalStandard: false,
      stats,
    })
    expect(state.kind).toBe('not_adopted')
    if (state.kind === 'not_adopted') {
      expect(state.clausesWithEvidence).toBe(16)
    }
    expect(standardProvenanceLabel(state)).not.toMatch(/fallback/i)
  })

  it('labels unavailable coverage as Coverage unavailable', () => {
    const state = standardCoverageState({
      coverageUnavailable: true,
      canonicalDataDegraded: false,
      canonicalDataMessage: null,
      hasCanonicalStandard: true,
      stats,
    })
    expect(state.kind).toBe('unavailable')
    expect(standardProvenanceLabel(state)).toBe('Coverage unavailable')
  })

  it('returns coverage percent when adopted', () => {
    const state = standardCoverageState({
      coverageUnavailable: false,
      canonicalDataDegraded: false,
      canonicalDataMessage: null,
      hasCanonicalStandard: true,
      stats,
    })
    expect(state.kind).toBe('coverage')
    if (state.kind === 'coverage') {
      expect(state.percent).toBe(Math.round(((10 + 6 * 0.5) / 117) * 100))
    }
  })

  it('explains ISO 27001 denominator split', () => {
    const note = clauseDenominatorNote({ management_clauses: 24, annex_a_controls: 93 })
    expect(note).toMatch(/117 clauses/)
    expect(note).toMatch(/93 Annex A/)
    expect(note).toMatch(/24 ISMS/)
  })
})
