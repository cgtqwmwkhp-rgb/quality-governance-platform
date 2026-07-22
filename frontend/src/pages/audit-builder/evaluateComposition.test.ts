import { describe, expect, it } from 'vitest'

import { filterApplicableSections, sectionIsApplicable } from './evaluateComposition'

describe('sectionIsApplicable', () => {
  it('is applicable when there are no rules', () => {
    expect(sectionIsApplicable(null, {})).toBe(true)
    expect(sectionIsApplicable(undefined, { assessmentMode: 'full' })).toBe(true)
  })

  it('is applicable when rule dimensions are empty arrays', () => {
    expect(
      sectionIsApplicable({ assessment_modes: [], asset_type_ids: [] }, { assessmentMode: 'full' }),
    ).toBe(true)
  })

  it('restricts by assessment_modes', () => {
    const rules = { assessment_modes: ['full', 'post_incident'] }
    expect(sectionIsApplicable(rules, { assessmentMode: 'full' })).toBe(true)
    expect(sectionIsApplicable(rules, { assessmentMode: 'spot_check' })).toBe(false)
    expect(sectionIsApplicable(rules, {})).toBe(false)
  })

  it('restricts by asset_type_ids', () => {
    const rules = { asset_type_ids: [1, 2] }
    expect(sectionIsApplicable(rules, { assetTypeId: 1 })).toBe(true)
    expect(sectionIsApplicable(rules, { assetTypeId: 3 })).toBe(false)
    expect(sectionIsApplicable(rules, {})).toBe(false)
  })

  it('requires both dimensions to match when both are configured', () => {
    const rules = { assessment_modes: ['full'], asset_type_ids: [1] }
    expect(sectionIsApplicable(rules, { assessmentMode: 'full', assetTypeId: 1 })).toBe(true)
    expect(sectionIsApplicable(rules, { assessmentMode: 'full', assetTypeId: 2 })).toBe(false)
    expect(sectionIsApplicable(rules, { assessmentMode: 'spot_check', assetTypeId: 1 })).toBe(false)
  })
})

describe('filterApplicableSections', () => {
  it('keeps only sections applicable to the given dimensions, preserving order', () => {
    const sections = [
      { id: 'a', applicabilityRules: null },
      { id: 'b', applicabilityRules: { assessment_modes: ['spot_check'] } },
      { id: 'c', applicabilityRules: { asset_type_ids: [9] } },
    ]
    expect(
      filterApplicableSections(sections, { assessmentMode: 'full', assetTypeId: 9 }).map((s) => s.id),
    ).toEqual(['a', 'c'])
  })
})
