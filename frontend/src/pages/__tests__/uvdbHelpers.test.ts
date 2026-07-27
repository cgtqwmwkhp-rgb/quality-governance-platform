import { describe, expect, it } from 'vitest'
import {
  UVDB_SECTION_IDS,
  UVDB_SECTIONS,
  buildUvdbBoardAlignment,
  formatUvdbAverageKpi,
  gateUvdbSectionScoreForDisplay,
  parseUvdbSection,
  uvdbPendingScoreExclusionCopy,
} from '../uvdbHelpers'

describe('uvdbHelpers', () => {
  it('defines five shell sections in display order', () => {
    expect(UVDB_SECTION_IDS).toEqual(['scores', 'protocol', 'audits', 'mapping', 'export'])
    expect(UVDB_SECTIONS.map((section) => section.id)).toEqual(UVDB_SECTION_IDS)
  })

  it('defaults to scores when section param is missing or invalid', () => {
    expect(parseUvdbSection(null)).toBe('scores')
    expect(parseUvdbSection('')).toBe('scores')
    expect(parseUvdbSection('dashboard')).toBe('scores')
  })

  it('opens audits when auditRef hint is present without a section', () => {
    expect(parseUvdbSection(null, { auditRefHint: true })).toBe('audits')
  })

  it('parses known section ids from the URL', () => {
    expect(parseUvdbSection('export')).toBe('export')
    expect(parseUvdbSection('mapping')).toBe('mapping')
  })

  it('PX-256: flags protocol vs Audits board count disagreement', () => {
    const alignment = buildUvdbBoardAlignment({
      protocolTotal: 3,
      protocolCompleted: 3,
      protocolAverage: 99,
      boardAchillesTotal: 12,
      scoredSources: ['imported', 'imported', 'imported'],
    })
    expect(alignment.countsDisagree).toBe(true)
    expect(alignment.averageProvenance).toBe('imported')
    expect(formatUvdbAverageKpi(alignment).caption).toMatch(/not verified/i)
  })

    it('PX-255 residual: labels mixed imported + calculated averages honestly', () => {
    const alignment = buildUvdbBoardAlignment({
      protocolTotal: 2,
      protocolCompleted: 2,
      protocolAverage: 80,
      boardAchillesTotal: 2,
      scoredSources: ['imported', 'calculated'],
    })
    expect(alignment.averageProvenance).toBe('mixed')
    expect(formatUvdbAverageKpi(alignment).value).toBe('80%')
  })

  it('PX-255 scoring policy: gates pending section scores out of display', () => {
    const gated = gateUvdbSectionScoreForDisplay(
      {
        score: 14,
        max_score: 15,
        percentage: 93.3,
        score_source: 'imported',
      },
      'pending_protocol_pdf',
    )
    expect(gated?.percentage).toBeNull()
    expect(gated?.score).toBeNull()
    expect(gated?.excluded_from_qualification).toBe(true)
    expect(uvdbPendingScoreExclusionCopy(gated?.exclusion_reason)).toMatch(/excluded from the qualification/i)
  })

  it('PX-255 scoring policy: loaded sections keep their percentage', () => {
    const gated = gateUvdbSectionScoreForDisplay(
      { score: 18, max_score: 21, percentage: 85.7, score_source: 'calculated' },
      'loaded',
    )
    expect(gated?.percentage).toBe(85.7)
    expect(gated?.excluded_from_qualification).toBeUndefined()
  })
})
