import { describe, expect, it } from 'vitest'
import {
  MAP_W2_SCHEME_CHIPS,
  computeIsoClauseCoverage,
  hasIsoClauseText,
  schemeChipStatus,
} from '../builderMapAssistHonesty'

describe('builderMapAssistHonesty MAP-W2', () => {
  it('exposes ISO / Planet Mark / UVDB scheme chips', () => {
    expect(MAP_W2_SCHEME_CHIPS).toEqual(['ISO', 'Planet Mark', 'UVDB'])
  })

  it('treats blank isoClause as uncovered', () => {
    expect(hasIsoClauseText(null)).toBe(false)
    expect(hasIsoClauseText('')).toBe(false)
    expect(hasIsoClauseText('  ')).toBe(false)
    expect(hasIsoClauseText('7.1.2')).toBe(true)
  })

  it('computes manual ISO clause coverage and keeps Assist accept chips offline', () => {
    const stats = computeIsoClauseCoverage([
      { isoClause: '7.1.2' },
      { isoClause: '' },
      { isoClause: '  ' },
      { isoClause: '8.1' },
    ])
    expect(stats).toEqual({
      totalQuestions: 4,
      withIsoClause: 2,
      isoCoveragePercent: 50,
      acceptedMultiSchemeLinks: 0,
      assistMapLive: false,
    })
  })

  it('marks ISO manual when clauses exist; Planet Mark / UVDB await Assist', () => {
    const stats = computeIsoClauseCoverage([{ isoClause: '7.1.2' }])
    expect(schemeChipStatus('ISO', stats)).toBe('manual_iso')
    expect(schemeChipStatus('Planet Mark', stats)).toBe('awaiting_assist')
    expect(schemeChipStatus('UVDB', stats)).toBe('awaiting_assist')
  })

  it('returns zero coverage for empty question lists', () => {
    expect(computeIsoClauseCoverage([])).toEqual({
      totalQuestions: 0,
      withIsoClause: 0,
      isoCoveragePercent: 0,
      acceptedMultiSchemeLinks: 0,
      assistMapLive: false,
    })
  })
})
