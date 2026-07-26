import { describe, expect, it } from 'vitest'

import { NOT_MEASURED, formatPercent } from './percentage'

describe('formatPercent', () => {
  it('renders an unmeasured percentage as the not-measured marker, not 0% or 100%', () => {
    expect(formatPercent(null)).toBe(NOT_MEASURED)
    expect(formatPercent(undefined)).toBe(NOT_MEASURED)
    expect(formatPercent(null)).not.toBe('0.0%')
    expect(formatPercent(null)).not.toBe('100.0%')
  })

  it('renders a genuine zero as 0%', () => {
    expect(formatPercent(0)).toBe('0.0%')
  })

  it('renders partial and full values', () => {
    expect(formatPercent(66.66)).toBe('66.7%')
    expect(formatPercent(100)).toBe('100.0%')
  })

  it('honours the requested precision', () => {
    expect(formatPercent(66.666, 2)).toBe('66.67%')
    expect(formatPercent(66.666, 0)).toBe('67%')
  })
})
