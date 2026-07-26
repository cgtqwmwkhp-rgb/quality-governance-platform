import { describe, expect, it } from 'vitest'
import {
  isAutomationTestTemplate,
  partitionAutomationTemplates,
} from '../auditTemplateHonesty'

describe('auditTemplateHonesty', () => {
  it('flags Playwright / CUJ / UAT fixture names (PX-219 / PX-266)', () => {
    expect(isAutomationTestTemplate({ name: 'Playwright CUJ audit template' })).toBe(true)
    expect(isAutomationTestTemplate({ name: 'CUJ-AT-08 sig' })).toBe(true)
    expect(isAutomationTestTemplate({ reference_number: 'CUJ-AT-10' })).toBe(true)
    expect(isAutomationTestTemplate({ name: 'UAT-THIN' })).toBe(true)
    expect(isAutomationTestTemplate({ name: 'Uat' })).toBe(true)
    expect(isAutomationTestTemplate({ name: 'TEST 3' })).toBe(true)
    expect(isAutomationTestTemplate({ name: 'Field Engineer Internal Audit (v4)' })).toBe(false)
    expect(isAutomationTestTemplate({ name: 'Quarterly Internal Audit (v3)' })).toBe(false)
  })

  it('partitions operational templates from automation fixtures', () => {
    const { operational, automation } = partitionAutomationTemplates([
      { name: 'Field Engineer Internal Audit (v4)' },
      { name: 'Playwright CUJ audit template' },
      { name: 'Quarterly Internal Audit (v3)' },
      { name: 'CUJ-AT-01' },
    ])
    expect(operational.map((t) => t.name)).toEqual([
      'Field Engineer Internal Audit (v4)',
      'Quarterly Internal Audit (v3)',
    ])
    expect(automation).toHaveLength(2)
  })
})
