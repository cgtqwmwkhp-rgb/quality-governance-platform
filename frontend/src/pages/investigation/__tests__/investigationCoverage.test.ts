import { describe, expect, it } from 'vitest'
import {
  buildSourceCoverageHonesty,
  sourceTypeLabel,
  type SourceCoverageResponse,
} from '../investigationCoverage'

function coverage(overrides: Partial<SourceCoverageResponse> = {}): SourceCoverageResponse {
  const items = overrides.items ?? [
    { source_type: 'reporting_incident', total: 27, investigated: 0, not_investigated: 27 },
    { source_type: 'near_miss', total: 4, investigated: 4, not_investigated: 0 },
  ]
  return {
    items,
    total: overrides.total ?? items.reduce((sum, i) => sum + i.total, 0),
    investigated: overrides.investigated ?? items.reduce((sum, i) => sum + i.investigated, 0),
    not_investigated:
      overrides.not_investigated ?? items.reduce((sum, i) => sum + i.not_investigated, 0),
  }
}

describe('buildSourceCoverageHonesty (PX-136)', () => {
  it('names the gap and refuses to treat the list as evidence of coverage', () => {
    const honesty = buildSourceCoverageHonesty(coverage())
    expect(honesty.hasGap).toBe(true)
    expect(honesty.headline).toBe('27 source records have no investigation')
    expect(honesty.detail).toContain('27 incidents')
    expect(honesty.detail).toContain('not evidence')
  })

  it('lists only registers with a gap, worst first', () => {
    const honesty = buildSourceCoverageHonesty(
      coverage({
        items: [
          { source_type: 'complaint', total: 5, investigated: 3, not_investigated: 2 },
          { source_type: 'reporting_incident', total: 9, investigated: 0, not_investigated: 9 },
          { source_type: 'near_miss', total: 2, investigated: 2, not_investigated: 0 },
        ],
      }),
    )
    expect(honesty.detail.indexOf('9 incidents')).toBeLessThan(honesty.detail.indexOf('2 complaints'))
    expect(honesty.detail).not.toContain('near miss')
  })

  it('stays silent when every record is investigated', () => {
    expect(
      buildSourceCoverageHonesty(
        coverage({
          items: [{ source_type: 'reporting_incident', total: 3, investigated: 3, not_investigated: 0 }],
        }),
      ).hasGap,
    ).toBe(false)
  })

  it('stays silent on empty registers and when coverage could not be read', () => {
    expect(buildSourceCoverageHonesty(coverage({ items: [] })).hasGap).toBe(false)
    expect(buildSourceCoverageHonesty(null).hasGap).toBe(false)
    expect(buildSourceCoverageHonesty(undefined).hasGap).toBe(false)
  })

  it('uses singular wording for a single record', () => {
    const honesty = buildSourceCoverageHonesty(
      coverage({
        items: [{ source_type: 'reporting_incident', total: 4, investigated: 3, not_investigated: 1 }],
      }),
    )
    expect(honesty.headline).toBe('1 source record has no investigation')
    expect(honesty.detail).toContain('1 incident.')
  })
})

describe('sourceTypeLabel', () => {
  it('pluralises near miss correctly', () => {
    expect(sourceTypeLabel('near_miss', 1)).toBe('near miss')
    expect(sourceTypeLabel('near_miss', 3)).toBe('near misses')
  })

  it('falls back to the raw key when the register is unknown', () => {
    expect(sourceTypeLabel('some_new_register', 2)).toBe('some new registers')
  })
})
