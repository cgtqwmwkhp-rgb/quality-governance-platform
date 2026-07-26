import { describe, expect, it } from 'vitest'
import {
  UVDB_SECTION_IDS,
  UVDB_SECTIONS,
  buildUvdbBoardAlignment,
  formatUvdbAverageKpi,
  parseUvdbSection,
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
})
