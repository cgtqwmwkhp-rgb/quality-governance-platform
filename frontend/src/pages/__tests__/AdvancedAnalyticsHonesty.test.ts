/**
 * The client half of C-7: a server that stops fabricating zeros is not enough.
 *
 * `/analytics/kpis` used to publish `training: { completion_rate: 0, ... }` from an
 * in-memory stub. Making the server honest — sending a discriminated union whose
 * unavailable branch carries no numeric field — fixes nothing on its own while this
 * page reads `Number(payload?.training?.completion_rate ?? 0)`, because `?? 0`
 * turns the absent field straight back into a confident 0%. That is the trap #1404
 * documented, and these tests pin the client side of it shut.
 *
 * The same applies to `trend`. The server sends null for the action and audit
 * trends because no period-over-period comparison is computed anywhere, and
 * `KPICard` renders 0 as a green "0%" no-change badge — a claim, not an absence.
 */
import { describe, it, expect } from 'vitest'

import { numberOrNull, numberOrUndefined, readTrainingMetric } from '../AdvancedAnalytics'

describe('readTrainingMetric', () => {
  it('reads a measured block as an ok metric', () => {
    const metric = readTrainingMetric({
      status: 'measured',
      completion_rate: 79.8,
      expiring_soon: 23,
      overdue: 369,
    })

    expect(metric).toEqual({
      status: 'ok',
      value: { completion_rate: 79.8, expiring_soon: 23, overdue: 369 },
    })
  })

  it('keeps a measured zero as a real zero', () => {
    // The fix narrows what 0 may mean; it must not stop it meaning anything. A
    // workforce whose every certificate has lapsed really is 0% compliant.
    const metric = readTrainingMetric({
      status: 'measured',
      completion_rate: 0,
      expiring_soon: 0,
      overdue: 4,
    })

    expect(metric).toEqual({
      status: 'ok',
      value: { completion_rate: 0, expiring_soon: 0, overdue: 4 },
    })
  })

  it('does not invent a zero for the unavailable branch', () => {
    // Exactly the payload the fixed server sends when nothing could be measured:
    // a status, a reason, and no number anywhere.
    const metric = readTrainingMetric({
      status: 'unavailable',
    } as { status?: string })

    expect(metric).toEqual({ status: 'unavailable' })
  })

  it('does not invent a zero when the block is missing entirely', () => {
    expect(readTrainingMetric(undefined)).toEqual({ status: 'unavailable' })
    expect(readTrainingMetric(null)).toEqual({ status: 'unavailable' })
  })

  it('branches on status rather than on the presence of a rate', () => {
    // Defence in depth. If a future server change adds `completion_rate: null` to
    // the unavailable branch, a client that tested for the field's presence would
    // silently start reporting 0% again. Branching on `status` cannot.
    const metric = readTrainingMetric({
      status: 'unavailable',
      completion_rate: null,
      expiring_soon: null,
      overdue: null,
    })

    expect(metric).toEqual({ status: 'unavailable' })
  })

  it('treats an unrecognised status as unmeasured rather than guessing', () => {
    const metric = readTrainingMetric({ status: 'partial', completion_rate: 50 })

    expect(metric).toEqual({ status: 'unavailable' })
  })
})

describe('numberOrNull', () => {
  it('passes a real number through, including zero', () => {
    expect(numberOrNull(79.8)).toBe(79.8)
    expect(numberOrNull(0)).toBe(0)
  })

  it('does not turn an absent value into zero', () => {
    // `Number(null ?? 0)` is 0, which is how the server's honest null became a
    // fabricated 0% on screen.
    expect(numberOrNull(null)).toBeNull()
    expect(numberOrNull(undefined)).toBeNull()
  })

  it('does not turn a non-finite value into a number', () => {
    expect(numberOrNull(Number.NaN)).toBeNull()
    expect(numberOrNull(Number.POSITIVE_INFINITY)).toBeNull()
  })
})

describe('numberOrUndefined', () => {
  it('keeps a measured trend, including a real zero', () => {
    expect(numberOrUndefined(-12.5)).toBe(-12.5)
    expect(numberOrUndefined(0)).toBe(0)
  })

  it('reports an uncomputed trend as undefined so no badge renders', () => {
    // KPICard guards on `trend !== undefined`. Null must therefore become
    // undefined, not 0, or the card shows a green "0%" for a trend nobody computed.
    expect(numberOrUndefined(null)).toBeUndefined()
    expect(numberOrUndefined(undefined)).toBeUndefined()
  })
})
