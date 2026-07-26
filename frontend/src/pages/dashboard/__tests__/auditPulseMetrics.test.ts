import { describe, expect, it } from 'vitest'
import { auditScoreMetricFromDashboard } from '../auditPulseMetrics'

describe('auditScoreMetricFromDashboard', () => {
  it('returns unavailable when avg_score is null (PX-183 / PX-194)', () => {
    expect(auditScoreMetricFromDashboard({ avg_score: null }).status).toBe('unavailable')
    expect(auditScoreMetricFromDashboard(undefined).status).toBe('unavailable')
  })

  it('rounds a live server average', () => {
    const metric = auditScoreMetricFromDashboard({ avg_score: 87.4 })
    expect(metric.status).toBe('ok')
    if (metric.status === 'ok') expect(metric.value).toBe(87)
  })
})
