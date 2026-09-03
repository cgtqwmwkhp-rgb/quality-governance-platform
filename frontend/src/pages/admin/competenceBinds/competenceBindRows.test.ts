import { describe, expect, it } from 'vitest'
import type {
  CompetenceAssessmentBind,
  CompetenceCharacteristic,
} from '../../../api/competenceBindClient'
import {
  BIND_CELL_TONE,
  apiErrorStatus,
  bindCellState,
  bindCellSummary,
  buildBindRows,
  intervalSummary,
} from './competenceBindRows'

function bind(overrides: Partial<CompetenceAssessmentBind> = {}): CompetenceAssessmentBind {
  return {
    id: 1,
    template_id: 8,
    characteristic_key: 'COUNTERBALANCE_FLT',
    mode: 'field',
    interval_days: 365,
    created_at: '2026-09-03T09:00:00Z',
    ...overrides,
  }
}

const CHARACTERISTICS: CompetenceCharacteristic[] = [
  { key: 'MEWP_3A', label: 'MEWP_3A' },
  { key: 'COUNTERBALANCE_FLT', label: 'COUNTERBALANCE_FLT' },
]

const templateName = (id: number) => (id === 8 ? 'FLT field assessment' : `Template #${id}`)

describe('buildBindRows', () => {
  it('lists every characteristic in the snapshot, bound or not', () => {
    const rows = buildBindRows(CHARACTERISTICS, [bind()])

    expect(rows.map((row) => row.key)).toEqual(['COUNTERBALANCE_FLT', 'MEWP_3A'])
    expect(rows[0].field).not.toBeNull()
    expect(rows[1].field).toBeNull()
    expect(rows[1].induction).toBeNull()
  })

  it('puts field and induction on the same characteristic row', () => {
    const rows = buildBindRows(CHARACTERISTICS, [
      bind(),
      bind({ id: 2, template_id: 12, mode: 'induction', interval_days: null }),
    ])

    const row = rows.find((entry) => entry.key === 'COUNTERBALANCE_FLT')!
    expect(row.field?.template_id).toBe(8)
    expect(row.induction?.template_id).toBe(12)
  })

  it('keeps a bind whose characteristic has left the snapshot, flagged as unmatched', () => {
    const rows = buildBindRows(CHARACTERISTICS, [bind({ characteristic_key: 'RETIRED_RIG' })])

    const orphan = rows[rows.length - 1]
    expect(orphan.key).toBe('RETIRED_RIG')
    expect(orphan.inSnapshot).toBe(false)
    expect(orphan.field).not.toBeNull()
    // The in-snapshot rows keep their own flag, so the badge cannot leak.
    expect(rows.filter((row) => row.inSnapshot).map((row) => row.key)).toEqual([
      'COUNTERBALANCE_FLT',
      'MEWP_3A',
    ])
  })

  it('degrades to an empty list rather than throwing on a malformed payload', () => {
    expect(buildBindRows(undefined as never, undefined as never)).toEqual([])
    expect(buildBindRows(CHARACTERISTICS, undefined as never)).toHaveLength(2)
  })

  it('does not match a field bind into the induction column', () => {
    const rows = buildBindRows([{ key: 'COUNTERBALANCE_FLT', label: 'COUNTERBALANCE_FLT' }], [bind()])

    expect(rows[0].induction).toBeNull()
  })
})

describe('unbound is not painted as a failure', () => {
  it('gives an unbound cell no fill and no destructive or muted-foreground colour', () => {
    const tone = BIND_CELL_TONE[bindCellState(null)]

    expect(tone).not.toContain('bg-destructive')
    expect(tone).not.toContain('bg-muted-foreground')
    expect(tone).toContain('bg-transparent')
  })

  it('never gives any bind state a destructive fill', () => {
    for (const tone of Object.values(BIND_CELL_TONE)) {
      expect(tone).not.toContain('bg-destructive')
      expect(tone).not.toContain('bg-muted-foreground')
    }
  })

  it('reports an unbound cell as an unmapped column, not a verdict', () => {
    const rows = buildBindRows(CHARACTERISTICS, [])

    const summary = bindCellSummary(rows[0], 'field', templateName)
    expect(summary).toContain('no template bound')
    expect(summary).not.toMatch(/fail|not competent|overdue/i)
  })
})

describe('intervalSummary', () => {
  it('reads a declared interval in days', () => {
    expect(intervalSummary(bind({ interval_days: 365 }))).toBe('reassess every 365 days')
    expect(intervalSummary(bind({ interval_days: 1 }))).toBe('reassess every day')
  })

  it('never calls an absent interval "never expires"', () => {
    const summary = intervalSummary(bind({ interval_days: null }))

    expect(summary).toContain('competency requirement')
    expect(summary).not.toMatch(/never/i)
  })

  it('says nothing at all for an unbound cell', () => {
    expect(intervalSummary(null)).toBe('')
  })
})

describe('bindCellSummary', () => {
  it('names the bound template and its interval', () => {
    const rows = buildBindRows(CHARACTERISTICS, [bind()])

    expect(bindCellSummary(rows[0], 'field', templateName)).toBe(
      'COUNTERBALANCE_FLT — field assessment — bound to FLT field assessment — reassess every 365 days',
    )
  })

  it('falls back to the template id when the published list cannot resolve it', () => {
    const rows = buildBindRows(CHARACTERISTICS, [bind({ template_id: 99 })])

    expect(bindCellSummary(rows[0], 'field', templateName)).toContain('Template #99')
  })
})

describe('apiErrorStatus', () => {
  it('reads an axios-shaped status without axios', () => {
    expect(apiErrorStatus({ response: { status: 404 } })).toBe(404)
  })

  it('returns null for anything else', () => {
    expect(apiErrorStatus(new Error('boom'))).toBeNull()
    expect(apiErrorStatus(null)).toBeNull()
    expect(apiErrorStatus({ response: {} })).toBeNull()
  })
})
