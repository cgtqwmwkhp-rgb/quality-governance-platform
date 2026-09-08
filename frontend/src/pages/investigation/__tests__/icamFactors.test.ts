/**
 * Pins the ICAM x HSG245 taxonomy the picker offers (INV-C12 / DEC-1).
 *
 * The categories and depths are listed in the frontend rather than fetched,
 * because DEC-1 settled them: four categories, three depths, no fifth. That is
 * only safe if a drift from the server enums is loud, so this suite asserts the
 * exact wire values and the exact order `ICAM_CATEGORY_ORDER` returns factors
 * in.
 *
 * Server side of the same contract:
 *   `FishboneCategory` / `CausalDepth` in `src/domain/models/rca_tools.py`
 *   `ICAM_CATEGORY_ORDER` in `src/domain/services/investigation_factors_service.py`
 *   `tests/unit/test_investigation_factors_api.py::test_icam_taxonomy_is_the_settled_four`
 */
import { describe, it, expect } from 'vitest'
import { CAUSAL_DEPTHS, ICAM_CATEGORIES, categoryLabel, depthLabel } from '../icamFactors'

describe('ICAM taxonomy', () => {
  it('offers the four ICAM categories, in the order the API returns them', () => {
    expect(ICAM_CATEGORIES.map((option) => option.value)).toEqual([
      'organisational_factors',
      'task_environmental_conditions',
      'individual_team_actions',
      'absent_failed_defences',
    ])
  })

  it('offers the three HSG245 causal depths, shallowest first', () => {
    expect(CAUSAL_DEPTHS.map((option) => option.value)).toEqual([
      'immediate',
      'underlying',
      'root',
    ])
  })

  it('gives every option a label and a hint, so no choice is unexplained', () => {
    for (const option of [...ICAM_CATEGORIES, ...CAUSAL_DEPTHS]) {
      expect(option.label.trim().length).toBeGreaterThan(0)
      expect(option.hint.trim().length).toBeGreaterThan(0)
    }
  })
})

describe('labels', () => {
  it('names a known category and shows an unknown one as stored', () => {
    expect(categoryLabel('absent_failed_defences')).toBe('Absent or failed defences')
    // A cause stored under a pre-DEC-1 6M category is shown as it is, not
    // relabelled into an ICAM category it was never filed under.
    expect(categoryLabel('manpower')).toBe('manpower')
  })

  it('says when no depth was recorded rather than inventing one', () => {
    expect(depthLabel('root')).toBe('Root')
    expect(depthLabel(null)).toBe('No depth recorded')
    expect(depthLabel('')).toBe('No depth recorded')
    expect(depthLabel(undefined)).toBe('No depth recorded')
  })
})
