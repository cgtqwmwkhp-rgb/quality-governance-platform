import { describe, expect, it } from 'vitest'
import { exceptionsHrefForClause } from '../Standards'

describe('exceptionsHrefForClause', () => {
  it('builds Knowledge Exceptions deep-link with clause + standard + operational', () => {
    expect(exceptionsHrefForClause('7.5', 'ISO9001')).toBe(
      '/knowledge-exceptions?clause=7.5&standard=ISO9001&operational=1',
    )
  })

  it('omits standard when not provided', () => {
    expect(exceptionsHrefForClause('8.1')).toBe(
      '/knowledge-exceptions?clause=8.1&operational=1',
    )
  })
})
