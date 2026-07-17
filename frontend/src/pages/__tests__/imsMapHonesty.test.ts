import { describe, expect, it } from 'vitest'
import {
  detectSchemesInMappings,
  isDemoSchemeReviewSource,
  MAP_W1_SCHEME_CHIPS,
} from '../imsMapHonesty'

describe('imsMapHonesty MAP-W1', () => {
  it('exposes ISO / Planet Mark / UVDB scheme chips', () => {
    expect(MAP_W1_SCHEME_CHIPS).toEqual(['ISO', 'Planet Mark', 'UVDB'])
  })

  it('detects schemes from live mapping labels', () => {
    expect(
      detectSchemesInMappings([
        { primary_standard: 'ISO 9001', mapped_standard: 'ISO 14001' },
        { primary_standard: 'Planet Mark', mapped_standard: 'UVDB Achilles' },
      ]),
    ).toEqual(['ISO', 'Planet Mark', 'UVDB'])
  })

  it('flags demo Planet Mark / UVDB review sources', () => {
    expect(isDemoSchemeReviewSource('Planet Mark')).toBe(true)
    expect(isDemoSchemeReviewSource('UVDB Achilles')).toBe(true)
    expect(isDemoSchemeReviewSource('ISO 9001')).toBe(false)
  })
})
