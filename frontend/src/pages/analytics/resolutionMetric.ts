/** Honest avg-resolution labelling for Analytics module rows (PX-225). */

export type ResolutionMetric =
  | { kind: 'days'; value: number; basis: 'register' | 'loaded_page' }
  | { kind: 'no_closed_items' }
  | { kind: 'not_measured' }
  | { kind: 'unavailable' }

export function resolutionFromAvgDays(
  days: number | null | undefined,
  basis: 'register' | 'loaded_page' = 'register',
): ResolutionMetric {
  if (days === undefined) return { kind: 'unavailable' }
  if (days === null) return { kind: 'no_closed_items' }
  if (!Number.isFinite(days)) return { kind: 'unavailable' }
  return { kind: 'days', value: days, basis }
}

export function formatResolutionMetric(m: ResolutionMetric): string {
  switch (m.kind) {
    case 'days':
      return `${m.value.toFixed(1)}d`
    case 'no_closed_items':
      return 'No closures'
    case 'not_measured':
      return 'Not measured'
    case 'unavailable':
      return '—'
  }
}

export function resolutionMetricNote(m: ResolutionMetric): string | null {
  switch (m.kind) {
    case 'days':
      return m.basis === 'loaded_page'
        ? 'Average from currently loaded register page'
        : 'Average across closed register records'
    case 'no_closed_items':
      return 'No closed records with usable timestamps'
    case 'not_measured':
      return 'This module does not expose closure timestamps here'
    case 'unavailable':
      return null
  }
}
