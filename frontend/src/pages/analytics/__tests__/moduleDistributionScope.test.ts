import { describe, expect, it } from 'vitest'
import {
  periodDistributionDenominator,
  periodDistributionPercent,
  rowsForPeriodDistribution,
} from '../moduleDistributionScope'

describe('moduleDistributionScope', () => {
  it('excludes register-only modules from the distribution denominator (PX-195)', () => {
    const rows = [
      { module: 'Incidents', distributionTotal: 22 },
      { module: 'Audits', distributionTotal: 8 },
      { module: 'Risks', distributionTotal: null },
      { module: 'Actions', distributionTotal: null },
    ]
    const eligible = rowsForPeriodDistribution(rows)
    expect(eligible.map((r) => r.module)).toEqual(['Incidents', 'Audits'])
    expect(periodDistributionDenominator(eligible)).toBe(30)
    expect(periodDistributionPercent(22, 30)).toBeCloseTo(73.33, 1)
  })
})
