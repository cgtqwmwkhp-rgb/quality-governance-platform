import type { LookupOption } from '../../api/lookupsClient'

export type LookupSelectOption = { value: string; label: string }

/**
 * Build select options from Admin Lookups, keeping defaults when the category
 * is empty so forms stay usable before configuration.
 * When lookups exist, union by code (lookup label wins) and append any
 * extra lookup codes not in the default set.
 */
export function mergeLookupSelectOptions(
  defaults: readonly LookupSelectOption[],
  lookupItems: LookupOption[] | undefined | null,
): LookupSelectOption[] {
  const items = (lookupItems || []).filter((item) => item.is_active !== false)
  if (items.length === 0) {
    return defaults.map((d) => ({ ...d }))
  }
  const byCode = new Map(items.map((item) => [item.code.toLowerCase(), item.label]))
  const seen = new Set<string>()
  const merged: LookupSelectOption[] = []
  for (const d of defaults) {
    const key = d.value.toLowerCase()
    seen.add(key)
    merged.push({ value: d.value, label: byCode.get(key) || d.label })
  }
  for (const item of items) {
    const key = item.code.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    merged.push({ value: item.code, label: item.label })
  }
  return merged
}
