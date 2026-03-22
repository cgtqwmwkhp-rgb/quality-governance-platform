import { describe, expect, it } from 'vitest'

import { formatScheduledDate, parseScheduledLocalDate } from '../dateUtils'

describe('parseScheduledLocalDate', () => {
  it('preserves day values for date-only strings', () => {
    const parsed = parseScheduledLocalDate('2026-03-22')

    expect(parsed).not.toBeNull()
    expect(parsed?.getFullYear()).toBe(2026)
    expect(parsed?.getMonth()).toBe(2)
    expect(parsed?.getDate()).toBe(22)
  })

  it('returns null for invalid values', () => {
    expect(parseScheduledLocalDate('not-a-date')).toBeNull()
    expect(parseScheduledLocalDate()).toBeNull()
  })

  it('formats date-only strings without shifting the day', () => {
    expect(formatScheduledDate('2026-03-22')).toContain('22')
  })
})
