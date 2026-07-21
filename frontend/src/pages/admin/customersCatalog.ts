/** Admin lookup category for organisation customers (dropdown SSOT). */
export const CUSTOMERS_LOOKUP_CATEGORY = 'customers' as const

/**
 * Suggested customer codes for admins — not pre-seeded; configure via Lookup Tables.
 * Forms should load options with lookupsApi.list(CUSTOMERS_LOOKUP_CATEGORY, true).
 */
export const CUSTOMER_CODE_HINTS = [
  { code: 'ukpn', label: 'UK Power Networks' },
  { code: 'openreach', label: 'Openreach' },
  { code: 'ssen', label: 'SSEN' },
  { code: 'national_grid', label: 'National Grid' },
] as const

export function customerHintCodes(): string {
  return CUSTOMER_CODE_HINTS.map((h) => h.code).join(', ')
}

export type CustomerLookupOption = {
  value: string
  label: string
}

/** Map active lookup rows into select options (code = value, label = display). */
export function toCustomerSelectOptions(
  items: Array<{ code: string; label: string; is_active?: boolean }>,
): CustomerLookupOption[] {
  return items
    .filter((item) => item.is_active !== false)
    .map((item) => ({
      value: item.code,
      label: item.label?.trim() || item.code,
    }))
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }))
}
