import { describe, expect, it } from 'vitest'
import { weeklyToSparkPoints } from '../PulseSparkline'

describe('weeklyToSparkPoints', () => {
  it('prefers value over count and drops null/NaN points', () => {
    const points = weeklyToSparkPoints([
      { week_start: '2026-01-01', count: 1, value: 10 },
      { week_start: '2026-01-08', count: 2, value: null },
      { week_start: '2026-01-15', count: 3 },
    ])
    expect(points).toEqual([
      { t: '2026-01-01', v: 10 },
      { t: '2026-01-15', v: 3 },
    ])
  })
})
