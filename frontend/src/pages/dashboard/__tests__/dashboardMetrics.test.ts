import { describe, it, expect } from 'vitest'
import {
  buildHighlightChips,
  computeRiskTrendDirection,
  countCreatedWithinDays,
  derivePersona,
  isMetricOk,
  metricFromSettled,
  metricOk,
  metricUnavailable,
  personaOrgStripIsCompact,
  personaShowsMyDay,
  personaShowsOrgStrip,
} from '../dashboardMetrics'

describe('Metric<T> fail-honest wrapper', () => {
  it('metricOk wraps a real value', () => {
    const m = metricOk(3)
    expect(isMetricOk(m)).toBe(true)
    expect(m).toEqual({ status: 'ok', value: 3 })
  })

  it('metricUnavailable never carries a fabricated value', () => {
    const m = metricUnavailable<number>()
    expect(isMetricOk(m)).toBe(false)
    expect(m).toEqual({ status: 'unavailable' })
  })

  it('metricFromSettled maps a fulfilled promise result to ok', () => {
    const result: PromiseSettledResult<{ data: number }> = {
      status: 'fulfilled',
      value: { data: 42 },
    }
    const m = metricFromSettled(result, (v) => v.data)
    expect(m).toEqual({ status: 'ok', value: 42 })
  })

  it('metricFromSettled maps a rejected promise to unavailable — never a silent 0', () => {
    const result: PromiseSettledResult<{ data: number }> = {
      status: 'rejected',
      reason: new Error('network down'),
    }
    const m = metricFromSettled(result, (v) => v.data)
    expect(m).toEqual({ status: 'unavailable' })
  })

  it('metricFromSettled maps a throwing selector to unavailable rather than crashing', () => {
    const result: PromiseSettledResult<{ data: number }> = {
      status: 'fulfilled',
      value: { data: 1 },
    }
    const m = metricFromSettled(result, () => {
      throw new Error('boom')
    })
    expect(m).toEqual({ status: 'unavailable' })
  })
})

describe('derivePersona (locked design §5)', () => {
  it('linked engineer with no org role -> engineer (My Day only)', () => {
    expect(derivePersona({ linked: true, isOrgRole: false })).toBe('engineer')
  })

  it('admin/manager without engineer link -> manager (Org first)', () => {
    expect(derivePersona({ linked: false, isOrgRole: true })).toBe('manager')
  })

  it('linked engineer who is also admin/manager -> dual (My Day first + compact org)', () => {
    expect(derivePersona({ linked: true, isOrgRole: true })).toBe('dual')
  })

  it('neither linked nor org role -> unlinked fallback (treated as org-first)', () => {
    expect(derivePersona({ linked: false, isOrgRole: false })).toBe('unlinked')
  })

  it('engineer persona shows My Day and does not show the org strip', () => {
    expect(personaShowsMyDay('engineer')).toBe(true)
    expect(personaShowsOrgStrip('engineer')).toBe(false)
  })

  it('manager persona shows the org strip but not My Day', () => {
    expect(personaShowsMyDay('manager')).toBe(false)
    expect(personaShowsOrgStrip('manager')).toBe(true)
  })

  it('dual persona shows both, with the org strip compact', () => {
    expect(personaShowsMyDay('dual')).toBe(true)
    expect(personaShowsOrgStrip('dual')).toBe(true)
    expect(personaOrgStripIsCompact('dual')).toBe(true)
    expect(personaOrgStripIsCompact('manager')).toBe(false)
  })

  it('unlinked persona falls back to the (non-compact) org strip', () => {
    expect(personaShowsMyDay('unlinked')).toBe(false)
    expect(personaShowsOrgStrip('unlinked')).toBe(true)
    expect(personaOrgStripIsCompact('unlinked')).toBe(false)
  })
})

describe('countCreatedWithinDays (pulse 7d counters)', () => {
  const now = new Date('2026-07-21T12:00:00Z')

  it('counts items created within the window', () => {
    const items = [
      { created_at: '2026-07-20T00:00:00Z' },
      { created_at: '2026-07-19T00:00:00Z' },
      { created_at: '2026-06-01T00:00:00Z' },
    ]
    expect(countCreatedWithinDays(items, 7, now)).toBe(2)
  })

  it('ignores items with missing or invalid created_at rather than throwing', () => {
    const items = [{ created_at: undefined }, { created_at: 'not-a-date' }, { created_at: null }]
    expect(countCreatedWithinDays(items as never, 7, now)).toBe(0)
  })
})

describe('computeRiskTrendDirection (org command risk+forecast)', () => {
  it('returns null when fewer than two points are available (fail-honest, no guess)', () => {
    expect(computeRiskTrendDirection([])).toBeNull()
    expect(computeRiskTrendDirection([{ avg_residual: 5 }])).toBeNull()
    expect(computeRiskTrendDirection(undefined)).toBeNull()
  })

  it('detects increasing residual risk', () => {
    expect(
      computeRiskTrendDirection([{ avg_residual: 5 }, { avg_residual: 7 }]),
    ).toBe('increasing')
  })

  it('detects decreasing residual risk', () => {
    expect(
      computeRiskTrendDirection([{ avg_residual: 7 }, { avg_residual: 5 }]),
    ).toBe('decreasing')
  })

  it('treats small deltas as stable', () => {
    expect(
      computeRiskTrendDirection([{ avg_residual: 5 }, { avg_residual: 5.02 }]),
    ).toBe('stable')
  })
})

describe('buildHighlightChips (Live Highlight Rail, fail-honest)', () => {
  it('emits nothing when every input is unavailable — never a fabricated zero chip', () => {
    const chips = buildHighlightChips({
      myDay: {
        clearState: metricUnavailable(),
        trainingGapCount: metricUnavailable(),
        myOverdueActions: metricUnavailable(),
      },
      org: {
        unassignedTotal: metricUnavailable(),
        criticalIncidentsOpen: metricUnavailable(),
        outsideAppetiteRisks: metricUnavailable(),
        assetsOverdue: metricUnavailable(),
        assetsQuarantined: metricUnavailable(),
      },
    })
    expect(chips).toEqual([])
  })

  it('emits nothing for real zero values (zero is not a priority, not an error)', () => {
    const chips = buildHighlightChips({
      myDay: {
        clearState: metricOk('clear'),
        trainingGapCount: metricOk(0),
        myOverdueActions: metricOk(0),
      },
      org: {
        unassignedTotal: metricOk(0),
        criticalIncidentsOpen: metricOk(0),
      },
    })
    expect(chips).toEqual([])
  })

  it('builds a blocked clear-to-work chip that deep-links to the tools page', () => {
    const chips = buildHighlightChips({ myDay: { clearState: metricOk('blocked') } })
    expect(chips).toHaveLength(1)
    expect(chips[0]).toMatchObject({ tone: 'critical', href: '/portal/tools' })
    expect(chips[0].label).toMatch(/not clear to work/i)
  })

  it('builds training-gap, overdue-action, and org chips with correct deep-links', () => {
    const chips = buildHighlightChips({
      myDay: {
        trainingGapCount: metricOk(2),
        myOverdueActions: metricOk(1),
      },
      org: {
        unassignedTotal: metricOk(3),
        criticalIncidentsOpen: metricOk(1),
        outsideAppetiteRisks: metricOk(4),
        assetsOverdue: metricOk(2),
        assetsQuarantined: metricOk(1),
      },
    })
    const byId = Object.fromEntries(chips.map((c) => [c.id, c]))
    expect(byId['my-training-gap'].href).toBe('/portal/work#training')
    expect(byId['my-overdue-actions'].href).toBe('/actions?view=my_overdue')
    expect(byId['org-unassigned'].href).toBe('/incidents?owner=unassigned')
    expect(byId['org-critical-incidents'].href).toBe('/incidents')
    expect(byId['org-risk-appetite'].href).toBe('/risk-register?hero=outside_appetite')
    expect(byId['org-assets-overdue'].href).toBe('/safety-assets/analytics')
    expect(byId['org-assets-quarantined'].href).toBe('/safety-assets/analytics')
    expect(chips).toHaveLength(7)
  })

  it('does not double-emit a chip when one signal failed but a sibling signal is fine', () => {
    const chips = buildHighlightChips({
      org: {
        unassignedTotal: metricUnavailable(),
        criticalIncidentsOpen: metricOk(2),
      },
    })
    expect(chips).toHaveLength(1)
    expect(chips[0].id).toBe('org-critical-incidents')
  })
})
