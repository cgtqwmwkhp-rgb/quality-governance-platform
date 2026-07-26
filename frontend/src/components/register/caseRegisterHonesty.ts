/**
 * Shared honesty helpers for case registers and detail pages (Run021 residual B).
 *
 * Keeps list ordering aligned with the date column the controller can see,
 * surfaces mixed reference formats without pretending minting is fixed, and
 * stops exposing opaque surrogate keys (`#132`, `Asset #40`) as if they were
 * case references.
 */

/** Parse an API date for sorting; unparseable / missing values sort last. */
export function parseCaseOccurredTime(value: string | number | Date | null | undefined): number {
  if (value == null || value === '') return Number.NEGATIVE_INFINITY
  if (value instanceof Date) {
    const ms = value.getTime()
    return Number.isNaN(ms) ? Number.NEGATIVE_INFINITY : ms
  }
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day).getTime()
  }
  const parsed = new Date(value)
  const ms = parsed.getTime()
  return Number.isNaN(ms) ? Number.NEGATIVE_INFINITY : ms
}

/**
 * Newest-first by the date the register actually shows (Occurred / Received).
 * Stable for equal dates via optional tie-breaker id.
 */
export function sortByOccurredDesc<T>(
  items: readonly T[],
  getOccurred: (item: T) => string | number | Date | null | undefined,
  getTieBreakId?: (item: T) => number | string | null | undefined,
): T[] {
  return [...items].sort((a, b) => {
    const delta = parseCaseOccurredTime(getOccurred(b)) - parseCaseOccurredTime(getOccurred(a))
    if (delta !== 0) return delta
    if (!getTieBreakId) return 0
    const idA = getTieBreakId(a)
    const idB = getTieBreakId(b)
    if (idA == null && idB == null) return 0
    if (idA == null) return 1
    if (idB == null) return -1
    if (typeof idA === 'number' && typeof idB === 'number') return idA - idB
    return String(idA).localeCompare(String(idB), 'en')
  })
}

/**
 * Legacy portal/mint path produced `INC-2026-CACDA723`-style suffixes (hex with
 * letters). The current sequential scheme is digits only after the year.
 */
export function isHexStyleCaseReference(reference: string | null | undefined): boolean {
  if (reference == null) return false
  const trimmed = String(reference).trim().toUpperCase()
  if (!trimmed) return false
  const match = trimmed.match(/^[A-Z]+-\d{4}-([0-9A-F]+)$/)
  if (!match) return false
  const suffix = match[1]
  return /[A-F]/.test(suffix)
}

export function isSequentialCaseReference(reference: string | null | undefined): boolean {
  if (reference == null) return false
  const trimmed = String(reference).trim().toUpperCase()
  if (!trimmed) return false
  return /^[A-Z]+-\d{4}-\d+$/.test(trimmed)
}

/** True when the visible page mixes sequential and hex-style references (PX-126). */
export function hasMixedCaseReferenceFormats(
  references: ReadonlyArray<string | null | undefined>,
): boolean {
  let sawSequential = false
  let sawHex = false
  for (const ref of references) {
    if (isHexStyleCaseReference(ref)) sawHex = true
    else if (isSequentialCaseReference(ref)) sawSequential = true
    if (sawSequential && sawHex) return true
  }
  return false
}

/**
 * Breadcrumb / chrome label: prefer the human reference; never fall back to
 * `#${surrogateId}` (PX-174).
 */
export function caseBreadcrumbLabel(
  reference: string | null | undefined,
  entityFallback: string,
): string {
  if (reference == null) return entityFallback
  const trimmed = String(reference).trim()
  return trimmed || entityFallback
}

/** Linked asset without exposing the numeric surrogate as a faux reference. */
export function linkedAssetDisplayLabel(assetId: number | null | undefined): string | null {
  if (assetId == null) return null
  return 'Linked asset'
}

/** Linked contract without `Contract #N`. */
export function linkedContractDisplayLabel(
  name: string | null | undefined,
  contractId: number | null | undefined,
): string {
  const trimmed = name != null ? String(name).trim() : ''
  if (trimmed) return trimmed
  if (contractId == null) return 'Not provided'
  return 'Contract on record'
}

/** Linked risk row title without `Risk #N`. */
export function linkedRiskDisplayLabel(riskId: number | null | undefined): string {
  if (riskId == null) return 'Linked risk'
  return 'Linked risk'
}
