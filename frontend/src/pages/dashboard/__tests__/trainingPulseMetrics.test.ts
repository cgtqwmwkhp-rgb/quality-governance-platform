import { describe, expect, it } from 'vitest'
import { trainingComplianceMetricFromSummary } from '../trainingPulseMetrics'

/**
 * The zero-requirement payload below is what staging returns today:
 * required_row_count 0 and person_count 0, so module_ok Overall is 0/0 and the
 * API reports pct 0 by convention.
 */
const NO_REQUIREMENTS_DEFINED = {
  module_ok: [{ role: 'Overall', ok: 0, total: 0, pct: 0, metric: 'module_ok' }],
}

describe('trainingComplianceMetricFromSummary', () => {
  it('reports unavailable when no requirements are defined, not 0% compliance', () => {
    expect(trainingComplianceMetricFromSummary(NO_REQUIREMENTS_DEFINED).status).toBe('unavailable')
  })

  it('reports unavailable when the Overall row is absent', () => {
    expect(
      trainingComplianceMetricFromSummary({
        module_ok: [{ role: 'Engineer', ok: 3, total: 4, pct: 75, metric: 'module_ok' }],
      }).status,
    ).toBe('unavailable')
    expect(trainingComplianceMetricFromSummary({ module_ok: [] }).status).toBe('unavailable')
    expect(trainingComplianceMetricFromSummary(undefined).status).toBe('unavailable')
  })

  it('reports a real percentage once a denominator exists', () => {
    const metric = trainingComplianceMetricFromSummary({
      module_ok: [{ role: 'Overall', ok: 41, total: 50, pct: 82, metric: 'module_ok' }],
    })
    expect(metric.status).toBe('ok')
    if (metric.status === 'ok') expect(metric.value).toBe(82)
  })

  it('still reports a genuine 0% when the denominator is real', () => {
    const metric = trainingComplianceMetricFromSummary({
      module_ok: [{ role: 'Overall', ok: 0, total: 50, pct: 0, metric: 'module_ok' }],
    })
    expect(metric.status).toBe('ok')
    if (metric.status === 'ok') expect(metric.value).toBe(0)
  })

  it('reports unavailable when total or pct is not a usable number', () => {
    expect(
      trainingComplianceMetricFromSummary({
        module_ok: [{ role: 'Overall', total: null, pct: null }],
      }).status,
    ).toBe('unavailable')
    expect(
      trainingComplianceMetricFromSummary({
        module_ok: [{ role: 'Overall', total: 50, pct: null }],
      }).status,
    ).toBe('unavailable')
  })
})
