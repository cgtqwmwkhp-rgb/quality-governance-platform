import { describe, expect, it } from 'vitest'
import { parseInterval } from '../RequirementFormDialog'

describe('parseInterval', () => {
  it('reads a whole number', () => {
    expect(parseInterval('12')).toBe(12)
  })

  it('treats an empty box as "no interval", not as an error', () => {
    expect(parseInterval('')).toBeNull()
    expect(parseInterval('   ')).toBeNull()
  })

  it('rejects zero, which the API refuses with ge=1', () => {
    expect(parseInterval('0')).toBeUndefined()
  })

  it('rejects a negative interval', () => {
    expect(parseInterval('-3')).toBeUndefined()
  })

  it('rejects a fractional interval rather than truncating it', () => {
    expect(parseInterval('1.5')).toBeUndefined()
  })

  it('rejects text, so a typo cannot become a silent null', () => {
    expect(parseInterval('twelve')).toBeUndefined()
    expect(parseInterval('12 months')).toBeUndefined()
  })

  it('rejects a value that Number() would happily coerce', () => {
    // Number('1e3') is 1000; the digit-only guard is what stops it.
    expect(parseInterval('1e3')).toBeUndefined()
  })

  it('accepts surrounding whitespace', () => {
    expect(parseInterval('  6  ')).toBe(6)
  })
})
