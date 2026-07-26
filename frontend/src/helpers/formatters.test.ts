import { describe, expect, it } from 'vitest'

import {
  NOT_PROVIDED,
  TREND_CAP_PERCENT,
  computeTrend,
  formatCount,
  formatDisplayDate,
  formatDisplayDateTime,
  formatReference,
  formatReferenceWithFallback,
  formatTrend,
  trendFromPercent,
} from './formatters'

describe('formatDisplayDate', () => {
  it('renders UK order regardless of the browser locale', () => {
    // Midday UTC so the assertion holds whatever timezone CI runs in.
    expect(formatDisplayDate('2026-07-24T12:00:00Z')).toBe('24/07/2026')
    expect(formatDisplayDate(new Date(2024, 9, 11))).toBe('11/10/2024')
  })

  it('zero-pads so column widths do not jitter', () => {
    expect(formatDisplayDate('2026-01-05')).toBe('05/01/2026')
  })

  it('treats a date-only string as local midnight, not UTC midnight', () => {
    // `new Date('2026-07-23')` is UTC midnight and renders as the 22nd west of
    // Greenwich. The calendar date the API sent must survive the round trip.
    expect(formatDisplayDate('2026-07-23')).toBe('23/07/2026')
  })

  it('returns the not-provided marker rather than "Invalid Date"', () => {
    expect(formatDisplayDate(null)).toBe(NOT_PROVIDED)
    expect(formatDisplayDate(undefined)).toBe(NOT_PROVIDED)
    expect(formatDisplayDate('')).toBe(NOT_PROVIDED)
    expect(formatDisplayDate('not a date')).toBe(NOT_PROVIDED)
    expect(formatDisplayDate(new Date('nope'))).toBe(NOT_PROVIDED)
  })
})

describe('formatDisplayDateTime', () => {
  it('renders UK order with a 24-hour clock', () => {
    expect(formatDisplayDateTime(new Date(2026, 6, 24, 14, 30))).toBe('24/07/2026, 14:30')
  })

  it('renders midnight as 00:00, never 24:00', () => {
    expect(formatDisplayDateTime(new Date(2026, 6, 24, 0, 0))).toBe('24/07/2026, 00:00')
  })

  it('returns the not-provided marker for missing input', () => {
    expect(formatDisplayDateTime(null)).toBe(NOT_PROVIDED)
    expect(formatDisplayDateTime('rubbish')).toBe(NOT_PROVIDED)
  })
})

describe('formatReference', () => {
  it('normalises case and whitespace to one format', () => {
    expect(formatReference(' inc-2026-0057 ')).toBe('INC-2026-0057')
    expect(formatReference('INC-2026-0057')).toBe('INC-2026-0057')
  })

  it('returns the not-provided marker for a missing reference', () => {
    expect(formatReference(null)).toBe(NOT_PROVIDED)
    expect(formatReference(undefined)).toBe(NOT_PROVIDED)
    expect(formatReference('   ')).toBe(NOT_PROVIDED)
  })
})

describe('formatReferenceWithFallback', () => {
  it('prefers the real reference', () => {
    expect(formatReferenceWithFallback('inv-2026-0003', 'INV', 12)).toBe('INV-2026-0003')
  })

  it('synthesises one consistent fallback shape when the record has none', () => {
    expect(formatReferenceWithFallback(null, 'INV', 12)).toBe('INV-12')
    expect(formatReferenceWithFallback('', 'act', 7)).toBe('ACT-7')
  })

  it('returns the not-provided marker when there is nothing to build from', () => {
    expect(formatReferenceWithFallback(null, 'INV', null)).toBe(NOT_PROVIDED)
  })
})

describe('computeTrend', () => {
  it('reports an empty baseline as no-baseline, never as a percentage', () => {
    // PX-224: the divide-by-zero branch is what produced absurd headline figures.
    expect(computeTrend(6, 0)).toEqual({ kind: 'no-baseline', current: 6 })
    expect(formatTrend(computeTrend(6, 0))).toBe('No baseline')
    expect(formatTrend(computeTrend(6, 0))).not.toContain('%')
  })

  it('reports nothing-then-nothing as a genuine no change', () => {
    expect(computeTrend(0, 0)).toEqual({ kind: 'change', percent: 0 })
    expect(formatTrend(computeTrend(0, 0))).toBe('No change')
  })

  it('treats absent or non-finite inputs as unknown, not as no change', () => {
    expect(computeTrend(null, 4)).toEqual({ kind: 'unknown' })
    expect(computeTrend(4, null)).toEqual({ kind: 'unknown' })
    expect(computeTrend(4, Number.NaN)).toEqual({ kind: 'unknown' })
    expect(computeTrend(Number.POSITIVE_INFINITY, 4)).toEqual({ kind: 'unknown' })
    expect(formatTrend(computeTrend(null, null))).toBe('No data')
  })

  it('computes an ordinary period-over-period change', () => {
    expect(formatTrend(computeTrend(12, 10))).toBe('+20.0%')
    expect(formatTrend(computeTrend(8, 10))).toBe('-20.0%')
    expect(formatTrend(computeTrend(10, 10))).toBe('No change')
  })

  it('caps pathological magnitudes instead of printing them in full', () => {
    expect(formatTrend(computeTrend(2000, 1))).toBe(`+>${TREND_CAP_PERCENT}%`)
    expect(formatTrend(computeTrend(6, 1))).toBe('+500.0%')
  })
})

describe('trendFromPercent', () => {
  it('passes a finite percentage through', () => {
    expect(formatTrend(trendFromPercent(-12.34))).toBe('-12.3%')
  })

  it('treats a missing or non-finite percentage as unknown', () => {
    expect(trendFromPercent(null)).toEqual({ kind: 'unknown' })
    expect(trendFromPercent(Number.NaN)).toEqual({ kind: 'unknown' })
  })
})

describe('formatCount', () => {
  it('groups thousands and marks absent counts', () => {
    expect(formatCount(12345)).toBe('12,345')
    expect(formatCount(0)).toBe('0')
    expect(formatCount(null)).toBe(NOT_PROVIDED)
    expect(formatCount(Number.NaN)).toBe(NOT_PROVIDED)
  })
})
