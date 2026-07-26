import { describe, expect, it } from 'vitest'
import {
  formatResolutionMetric,
  resolutionFromAvgDays,
  resolutionMetricNote,
} from '../resolutionMetric'
import { scopeCaption, scopeLabel } from '../moduleScope'

describe('resolutionMetric (PX-225)', () => {
  it('formats register days', () => {
    const m = resolutionFromAvgDays(4.25, 'register')
    expect(formatResolutionMetric(m)).toBe('4.3d')
    expect(resolutionMetricNote(m)).toMatch(/closed register/i)
  })

  it('distinguishes no closures from not measured and unavailable', () => {
    expect(formatResolutionMetric(resolutionFromAvgDays(null))).toBe('No closures')
    expect(formatResolutionMetric({ kind: 'not_measured' })).toBe('Not measured')
    expect(formatResolutionMetric(resolutionFromAvgDays(undefined))).toBe('—')
  })
})

describe('moduleScope (PX-226)', () => {
  it('labels register vs period', () => {
    expect(scopeLabel('register')).toBe('Register')
    expect(scopeLabel('period')).toBe('Period')
    expect(scopeCaption('Last 30 days')).toMatch(/register-wide/i)
  })
})
