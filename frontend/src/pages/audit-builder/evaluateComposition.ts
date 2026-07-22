/**
 * FE mirror of `src/domain/services/audit_composition.py`.
 *
 * Determines which sections/questions are in scope for a given audit run based on
 * the run's `assessment_mode` / `asset_type_id` dimensions and each section's
 * `applicability_rules` (`{assessment_modes, asset_type_ids}`). `null`/empty on a
 * rule dimension means that dimension is unrestricted (always applicable). A
 * question inherits its section's applicability.
 */

export interface CompositionRules {
  assessment_modes?: string[] | null
  asset_type_ids?: number[] | null
}

export interface CompositionDimensions {
  assessmentMode?: string | null
  assetTypeId?: number | null
}

function normalizeRuleList<T>(raw: T[] | null | undefined): T[] | null {
  if (!raw || raw.length === 0) return null
  return raw
}

/** Return true when a section with `rules` is in scope for the given run dimensions. */
export function sectionIsApplicable(
  rules: CompositionRules | null | undefined,
  { assessmentMode, assetTypeId }: CompositionDimensions,
): boolean {
  if (!rules) return true

  const allowedModes = normalizeRuleList(rules.assessment_modes)
  if (allowedModes !== null) {
    if (!assessmentMode || !allowedModes.includes(assessmentMode)) return false
  }

  const allowedAssetTypes = normalizeRuleList(rules.asset_type_ids)
  if (allowedAssetTypes !== null) {
    if (assetTypeId == null || !allowedAssetTypes.includes(assetTypeId)) return false
  }

  return true
}

/** Filter `sections` (or any list carrying `applicabilityRules`) down to the ones
 * applicable for the given run dimensions. Order is preserved. */
export function filterApplicableSections<T extends { applicabilityRules?: CompositionRules | null }>(
  sections: T[],
  dimensions: CompositionDimensions,
): T[] {
  return sections.filter((section) => sectionIsApplicable(section.applicabilityRules, dimensions))
}
