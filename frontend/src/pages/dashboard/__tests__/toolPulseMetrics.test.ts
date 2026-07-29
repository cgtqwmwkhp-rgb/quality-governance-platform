import { describe, expect, it } from 'vitest'
import { toolComplianceMetricFromSummary } from '../toolPulseMetrics'

const EMPTY_REGISTRY = {
  total: 0,
  expiry_bands: { overdue: 0, due_30: 0, due_60: 0, due_90: 0, in_date: 0 },
  by_type: {},
  by_status: { quarantined: 0 },
  generated_at: '2026-07-21T00:00:00Z',
}

describe('toolComplianceMetricFromSummary', () => {
  it('reports unavailable for an empty registry, not 100% compliance', () => {
    expect(toolComplianceMetricFromSummary(EMPTY_REGISTRY).status).toBe('unavailable')
  })

  it('reports unavailable when the summary or its total is absent', () => {
    expect(toolComplianceMetricFromSummary(undefined).status).toBe('unavailable')
    expect(toolComplianceMetricFromSummary(null).status).toBe('unavailable')
    // Number(null) is a finite 0, so the null check has to precede the conversion.
    expect(toolComplianceMetricFromSummary({ total: null }).status).toBe('unavailable')
  })

  it('computes the percentage from overdue and quarantined counts', () => {
    const metric = toolComplianceMetricFromSummary({
      total: 20,
      expiry_bands: { overdue: 3 },
      by_status: { quarantined: 1 },
    })
    expect(metric.status).toBe('ok')
    if (metric.status === 'ok') expect(metric.value).toBe(80)
  })

  it('treats missing bands as zero rather than as unavailable', () => {
    const metric = toolComplianceMetricFromSummary({ total: 4 })
    expect(metric.status).toBe('ok')
    if (metric.status === 'ok') expect(metric.value).toBe(100)
  })

  it('reports a genuine 0% when every asset is overdue', () => {
    const metric = toolComplianceMetricFromSummary({
      total: 5,
      expiry_bands: { overdue: 5 },
      by_status: { quarantined: 0 },
    })
    expect(metric.status).toBe('ok')
    if (metric.status === 'ok') expect(metric.value).toBe(0)
  })

  it('clamps rather than going negative when an asset is both overdue and quarantined', () => {
    const metric = toolComplianceMetricFromSummary({
      total: 2,
      expiry_bands: { overdue: 2 },
      by_status: { quarantined: 2 },
    })
    expect(metric.status).toBe('ok')
    if (metric.status === 'ok') expect(metric.value).toBe(0)
  })
})
