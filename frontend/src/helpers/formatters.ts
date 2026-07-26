/**
 * Shared display formatters for dates, reference codes and trend percentages.
 *
 * Before this module every list page carried its own private copy of
 * `new Date(x).toLocaleDateString()`, which resolves against the *browser*
 * locale — so the same incident rendered as 24/07/2026 for a UK reviewer and
 * 7/24/2026 for anyone whose machine is set to en-US. Reference codes and
 * trend percentages had the same problem. Import from here instead of
 * hand-rolling per page.
 *
 * Percentages that represent "nothing was measured" keep the PX-216 contract:
 * see `src/utils/percentage.ts`, which this module re-exports rather than
 * duplicating.
 */

import { NOT_MEASURED, formatPercent } from '../utils/percentage'

export { NOT_MEASURED, formatPercent }

/** Product standard: the platform is UK-first and every explicit locale in the codebase is en-GB. */
const DISPLAY_LOCALE = 'en-GB'

/** Shown wherever a value is absent — matches the not-measured marker used for metrics. */
export const NOT_PROVIDED = '—'

/** A bare calendar date with no time component, e.g. "2026-07-23". */
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/

/**
 * Parse an API date value.
 *
 * Date-only strings are deliberately built as *local* midnight. `new Date('2026-07-23')`
 * is parsed by the spec as UTC midnight, which renders as the 22nd for any user west of
 * Greenwich — an off-by-one on a value that never had a timezone in the first place.
 */
function parseDate(value: string | number | Date | null | undefined): Date | null {
  if (value == null || value === '') return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value

  if (typeof value === 'string' && DATE_ONLY.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day)
  }

  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

/** Format a date as DD/MM/YYYY. Returns the not-provided marker for missing or unparseable input. */
export function formatDisplayDate(value: string | number | Date | null | undefined): string {
  const date = parseDate(value)
  if (!date) return NOT_PROVIDED
  return date.toLocaleDateString(DISPLAY_LOCALE, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

/** Format a date and time as DD/MM/YYYY, HH:mm. Returns the not-provided marker for missing input. */
export function formatDisplayDateTime(value: string | number | Date | null | undefined): string {
  const date = parseDate(value)
  if (!date) return NOT_PROVIDED
  return date.toLocaleString(DISPLAY_LOCALE, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    // h23 explicitly: `hour12: false` renders midnight as 24:00 under some ICU builds.
    hourCycle: 'h23',
  })
}

/**
 * Normalise a reference code for display, e.g. " inc-2026-0057 " -> "INC-2026-0057".
 *
 * References are uppercase identifiers everywhere they are minted server-side; pages
 * that echoed user- or import-supplied values were rendering mixed case and stray
 * whitespace. Returns the not-provided marker when there is no reference.
 */
export function formatReference(value: string | null | undefined): string {
  if (value == null) return NOT_PROVIDED
  const trimmed = String(value).trim()
  if (!trimmed) return NOT_PROVIDED
  return trimmed.toUpperCase()
}

/**
 * Format a reference, falling back to a synthesised `PREFIX-id` when the record has none.
 *
 * Pages previously invented their own fallbacks (`INV-12`, `Action #12`, bare `12`),
 * so the same missing-reference case read three different ways.
 */
export function formatReferenceWithFallback(
  value: string | null | undefined,
  prefix: string,
  id: number | string | null | undefined,
): string {
  const formatted = formatReference(value)
  if (formatted !== NOT_PROVIDED) return formatted
  if (id == null || id === '') return NOT_PROVIDED
  return `${prefix.toUpperCase()}-${id}`
}

/**
 * A period-over-period comparison.
 *
 * `no-baseline` exists because "6 near misses this month, 0 last month" is a real
 * change that simply cannot be stated as a percentage. Collapsing it to 0% ("No
 * change") or to an invented 100% both assert something the data does not support.
 */
export type Trend =
  | { kind: 'unknown' }
  | { kind: 'no-baseline'; current: number }
  | { kind: 'change'; percent: number }

/** Percentages beyond this are reported as capped rather than printed in full. */
export const TREND_CAP_PERCENT = 999

/**
 * Compare a period against its predecessor.
 *
 * A zero baseline yields `no-baseline`, never a percentage: dividing by it is what
 * produced the fabricated "100%" server-side and the absurd magnitudes on screen.
 */
export function computeTrend(
  current: number | null | undefined,
  previous: number | null | undefined,
): Trend {
  if (current == null || previous == null) return { kind: 'unknown' }
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return { kind: 'unknown' }
  if (previous === 0) {
    return current === 0 ? { kind: 'change', percent: 0 } : { kind: 'no-baseline', current }
  }
  return { kind: 'change', percent: ((current - previous) / previous) * 100 }
}

/**
 * Wrap a percentage the API already calculated.
 *
 * Use `computeTrend` in preference. This exists for payloads that expose only a
 * percentage; a non-finite value is treated as unknown rather than rendered.
 */
export function trendFromPercent(percent: number | null | undefined): Trend {
  if (percent == null || !Number.isFinite(percent)) return { kind: 'unknown' }
  return { kind: 'change', percent }
}

/** Human-readable trend text: "No data", "No baseline", "No change", or a capped percentage. */
export function formatTrend(trend: Trend): string {
  switch (trend.kind) {
    case 'unknown':
      return 'No data'
    case 'no-baseline':
      return 'No baseline'
    case 'change': {
      if (trend.percent === 0) return 'No change'
      const sign = trend.percent > 0 ? '+' : '-'
      const magnitude = Math.abs(trend.percent)
      if (magnitude > TREND_CAP_PERCENT) return `${sign}>${TREND_CAP_PERCENT}%`
      return `${sign}${magnitude.toFixed(1)}%`
    }
  }
}

/** Format a count for display, or the not-provided marker when it is absent. */
export function formatCount(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return NOT_PROVIDED
  return new Intl.NumberFormat(DISPLAY_LOCALE).format(value)
}
