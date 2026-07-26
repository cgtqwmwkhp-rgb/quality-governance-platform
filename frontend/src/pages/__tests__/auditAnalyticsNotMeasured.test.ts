import { describe, expect, it } from 'vitest'

import { essentialComplianceAccent } from '../AuditAnalytics'
import { NOT_MEASURED, formatPercent } from '../../utils/percentage'

/**
 * PX-216: with an empty dataset the API returns null for every rate, and the
 * page must show "not measured" in a neutral colour — never a green 100%.
 */
describe('AuditAnalytics empty-dataset rendering', () => {
  const emptySummary = {
    period_days: 90,
    totals: 0,
    completed: 0,
    in_progress: 0,
    avg_score: null,
    pass_rate: null,
    essential_compliance_pct: null,
    incomplete_critical_count: 0,
  }

  it('renders every headline rate as not measured', () => {
    expect(formatPercent(emptySummary.pass_rate)).toBe(NOT_MEASURED)
    expect(formatPercent(emptySummary.essential_compliance_pct)).toBe(NOT_MEASURED)
    expect(formatPercent(emptySummary.avg_score)).toBe(NOT_MEASURED)
  })

  it('does not colour unmeasured essential compliance as a pass or a breach', () => {
    expect(essentialComplianceAccent(emptySummary.essential_compliance_pct)).toBe(
      'text-muted-foreground',
    )
    expect(essentialComplianceAccent(99)).toBe('text-success')
    expect(essentialComplianceAccent(80)).toBe('text-destructive')
  })
})
