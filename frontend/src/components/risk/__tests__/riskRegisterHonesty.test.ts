import { describe, expect, it } from 'vitest'
import {
  buildImportTriageHonesty,
  buildNeverReviewedHonesty,
  canAcceptImportTriage,
} from '../riskRegisterHonesty'
import { buildDocumentControlEmptyCopy } from '../documentControlHonesty'

describe('buildNeverReviewedHonesty (PX-157)', () => {
  it('hides when none are never-reviewed', () => {
    expect(buildNeverReviewedHonesty(0, 10).show).toBe(false)
  })

  it('surfaces counts when never-reviewed dominate', () => {
    const result = buildNeverReviewedHonesty(126, 129)
    expect(result.show).toBe(true)
    expect(result.message).toContain('126 of 129')
    expect(result.message).toMatch(/Outside Appetite/i)
    expect(result.message).toMatch(/not assurance/i)
  })
})

describe('buildImportTriageHonesty (PX-264)', () => {
  it('hides when triage queue empty', () => {
    expect(buildImportTriageHonesty({ pendingTotal: 0, risks: [] }).show).toBe(false)
  })

  it('reports unassigned + age for pending backlog', () => {
    const now = Date.parse('2026-07-26T12:00:00Z')
    const result = buildImportTriageHonesty({
      pendingTotal: 73,
      nowMs: now,
      risks: [
        { risk_owner_name: null, created_at: '2026-04-06T10:00:00Z' },
        { risk_owner_name: 'Alex', created_at: '2026-04-08T10:00:00Z' },
        { risk_owner_name: '  ', created_at: '2026-06-01T10:00:00Z' },
      ],
    })
    expect(result.show).toBe(true)
    expect(result.unassignedLoaded).toBe(2)
    expect(result.oldestAgeDays).toBeGreaterThanOrEqual(100)
    expect(result.message).toMatch(/73 import-sourced/)
    expect(result.message).toMatch(/unassigned/)
    expect(result.message).toMatch(/accept requires an owner/i)
  })

  it('blocks accept without owner', () => {
    expect(canAcceptImportTriage({ risk_owner_name: null })).toBe(false)
    expect(canAcceptImportTriage({ risk_owner_name: '  ' })).toBe(false)
    expect(canAcceptImportTriage({ risk_owner_name: 'Owner' })).toBe(true)
  })
})

describe('buildDocumentControlEmptyCopy (PX-263)', () => {
  it('distinguishes filtered empty from unpopulated', () => {
    const filtered = buildDocumentControlEmptyCopy({
      hasActiveFilters: true,
      libraryDocumentCount: 4,
    })
    expect(filtered.kind).toBe('filtered')
    expect(filtered.title).toMatch(/match these filters/i)

    const empty = buildDocumentControlEmptyCopy({
      hasActiveFilters: false,
      libraryDocumentCount: 4,
    })
    expect(empty.kind).toBe('unpopulated')
    expect(empty.description).toMatch(/ISO 9001/)
    expect(empty.description).toContain('4 documents')
    expect(empty.description).toMatch(/Library/)
  })
})
