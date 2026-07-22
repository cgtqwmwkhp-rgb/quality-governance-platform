import { describe, expect, it } from 'vitest'

import { formatCriticalQueueHeading } from '../AuditAnalytics'

describe('formatCriticalQueueHeading', () => {
  it('uses the uncapped KPI total when the list is capped', () => {
    expect(formatCriticalQueueHeading(350, 200)).toBe(
      'Critical items queue (showing 200 of 350)',
    )
  })

  it('shows a single count when the list is not capped', () => {
    expect(formatCriticalQueueHeading(12, 12)).toBe('Critical items queue (12)')
  })

  it('falls back to shown count when summary is unavailable', () => {
    expect(formatCriticalQueueHeading(undefined, 0)).toBe('Critical items queue (0)')
  })
})
