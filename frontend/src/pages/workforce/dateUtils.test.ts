import { describe, expect, it } from 'vitest'
import { formatScheduledDate, parseScheduledLocalDate } from './dateUtils'

describe('parseScheduledLocalDate', () => {
  it('returns null for empty values', () => {
    expect(parseScheduledLocalDate()).toBeNull()
    expect(parseScheduledLocalDate('')).toBeNull()
  })

  it('parses YYYY-MM-DD as local calendar date', () => {
    const d = parseScheduledLocalDate('2026-07-11')
    expect(d).not.toBeNull()
    expect(d!.getFullYear()).toBe(2026)
    expect(d!.getMonth()).toBe(6)
    expect(d!.getDate()).toBe(11)
  })

  it('parses ISO timestamps and rejects invalid', () => {
    expect(parseScheduledLocalDate('2026-07-11T12:00:00Z')).toBeInstanceOf(Date)
    expect(parseScheduledLocalDate('not-a-date')).toBeNull()
  })

  it('handles leap-day calendar date', () => {
    const d = parseScheduledLocalDate('2024-02-29')
    expect(d).not.toBeNull()
    expect(d!.getMonth()).toBe(1)
    expect(d!.getDate()).toBe(29)
  })
})

describe('formatScheduledDate', () => {
  it('formats valid dates and falls back for missing', () => {
    expect(formatScheduledDate('2026-07-11')).not.toBe('—')
    expect(formatScheduledDate()).toBe('—')
    expect(formatScheduledDate('nope')).toBe('—')
    expect(formatScheduledDate('2026-07-11T00:00:00Z')).not.toBe('—')
  })
})
