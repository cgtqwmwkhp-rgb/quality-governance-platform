import type { LookupOption } from '../../api/lookupsClient'

export type LookupSelectOption = { value: string; label: string }

/**
 * Overlay Admin Lookup labels onto a fixed default option set.
 * Does not append unknown codes — complaint/incident type and severity are
 * API enums; extra Admin codes would fail create validation.
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
  return defaults.map((d) => ({
    value: d.value,
    label: byCode.get(d.value.toLowerCase()) || d.label,
  }))
}
