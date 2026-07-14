import { describe, expect, it } from 'vitest'
import { parseLinkedRiskIds, riskRegisterHref } from '../nearMissRiskLinks'

describe('nearMissRiskLinks', () => {
  it('parses linked risk ids', () => {
    expect(parseLinkedRiskIds(undefined)).toEqual([])
    expect(parseLinkedRiskIds('1, 2,2,x,3')).toEqual([1, 2, 3])
  })

  it('builds risk register deep link', () => {
    expect(riskRegisterHref(9)).toBe('/risk-register?riskId=9')
  })
})
