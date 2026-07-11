import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  cn,
  decodeHtmlEntities,
  debounce,
  formatDate,
  formatDateTime,
  formatNumber,
  getInitials,
  sleep,
  truncate,
} from './utils'

describe('cn', () => {
  it('merges class names and dedupes tailwind conflicts', () => {
    expect(cn('px-2', false && 'hidden', 'px-4')).toContain('px-4')
    expect(cn('px-2', 'px-4')).not.toContain('px-2')
  })
})

describe('formatDate / formatDateTime / formatNumber', () => {
  it('formats date strings and Date objects', () => {
    const formatted = formatDate('2026-07-11T12:00:00Z')
    expect(formatted).toMatch(/2026/)
    expect(formatDate(new Date('2026-01-15'))).toMatch(/2026|Jan|15/)
  })

  it('formats date-time and numbers', () => {
    expect(formatDateTime('2026-07-11T12:30:00Z')).toMatch(/2026/)
    expect(formatNumber(1234.5)).toMatch(/1/)
  })
})

describe('truncate', () => {
  it('returns original when under limit', () => {
    expect(truncate('abc', 5)).toBe('abc')
  })

  it('appends ellipsis when over limit', () => {
    expect(truncate('abcdef', 3)).toBe('abc...')
  })
})

describe('getInitials', () => {
  it('builds up to two uppercase initials', () => {
    expect(getInitials('Ada Lovelace')).toBe('AL')
    expect(getInitials('Prince')).toBe('P')
    expect(getInitials('Jean Luc Picard')).toBe('JL')
  })
})

describe('decodeHtmlEntities', () => {
  it('passthrough without entities', () => {
    expect(decodeHtmlEntities('plain')).toBe('plain')
    expect(decodeHtmlEntities('')).toBe('')
  })

  it('decodes common entities', () => {
    expect(decodeHtmlEntities('A &amp; B')).toBe('A & B')
  })
})

describe('sleep', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('resolves after wait', async () => {
    vi.useFakeTimers()
    const p = sleep(25)
    vi.advanceTimersByTime(25)
    await expect(p).resolves.toBeUndefined()
  })
})

describe('debounce', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('invokes once after wait', () => {
    vi.useFakeTimers()
    const fn = vi.fn()
    const d = debounce(fn, 50)
    d('a')
    d('b')
    expect(fn).not.toHaveBeenCalled()
    vi.advanceTimersByTime(50)
    expect(fn).toHaveBeenCalledTimes(1)
    expect(fn).toHaveBeenCalledWith('b')
  })
})
