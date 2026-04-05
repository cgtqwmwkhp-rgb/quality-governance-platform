import { describe, expect, it } from 'vitest'
import {
  riskRegisterBowtieElementPath,
  riskRegisterBowtieElementsPath,
  riskRegisterKriValuePath,
} from './riskRegisterPaths'

describe('riskRegisterPaths', () => {
  it('bowtie element collection matches OpenAPI POST path', () => {
    expect(riskRegisterBowtieElementsPath(12)).toBe('/api/v1/risk-register/12/bowtie/elements')
  })

  it('bowtie element item matches OpenAPI DELETE path', () => {
    expect(riskRegisterBowtieElementPath(12, 99)).toBe('/api/v1/risk-register/12/bowtie/elements/99')
  })

  it('KRI value matches OpenAPI PUT path', () => {
    expect(riskRegisterKriValuePath(5)).toBe('/api/v1/risk-register/kris/5/value')
  })
})
