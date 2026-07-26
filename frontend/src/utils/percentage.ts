/**
 * Presentation side of `src/domain/metrics.py` (PX-216).
 *
 * The API returns `null` for a percentage whose denominator was zero — nothing
 * was measured. That must never be rendered as `0%` or `100%`, both of which
 * assert a compliance position the platform has no evidence for. Render the
 * not-measured marker instead.
 */

/** Shown wherever a metric exists but has no data behind it. */
export const NOT_MEASURED = '—'

/** Format a percentage, or the not-measured marker when the value is absent. */
export function formatPercent(value: number | null | undefined, digits = 1): string {
  return value == null ? NOT_MEASURED : `${value.toFixed(digits)}%`
}
