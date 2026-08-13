import { describe, expect, it } from 'vitest'
import {
  notifyBandForDays,
  pickSoonestMatchingObligation,
} from '../scheduleOpsPick'

describe('notifyBandForDays', () => {
  it('matches Schedule classify_due_band windows', () => {
    expect(notifyBandForDays(-1)).toBe('overdue')
    expect(notifyBandForDays(0)).toBe('due_7')
    expect(notifyBandForDays(7)).toBe('due_7')
    expect(notifyBandForDays(8)).toBe('due_30')
    expect(notifyBandForDays(30)).toBe('due_30')
    expect(notifyBandForDays(31)).toBe('due_60')
    expect(notifyBandForDays(60)).toBe('due_60')
    expect(notifyBandForDays(61)).toBe('none')
  })
})

describe('pickSoonestMatchingObligation', () => {
  const iso9001Legal = {
    reference_number: 'CSR-2026-0001',
    title: 'Legal register (ISO 9001 6.1.3)',
    regulatory_basis: 'ISO 9001',
    owner_name: 'Alex Owner',
    next_due_date: '2026-09-01',
    status: 'current' as const,
  }
  const laterMatch = {
    ...iso9001Legal,
    reference_number: 'CSR-2026-0002',
    next_due_date: '2026-12-01',
    owner_name: 'Later Person',
  }
  const unrelated = {
    reference_number: 'CSR-2026-0099',
    title: 'Fire risk assessment',
    regulatory_basis: 'RRFSO',
    owner_name: 'Fire Owner',
    next_due_date: '2026-08-14',
    status: 'due_soon' as const,
  }

  it('returns the soonest clause match and does not invent an owner', () => {
    const pick = pickSoonestMatchingObligation(
      [laterMatch, unrelated, iso9001Legal],
      '6.1.3',
      '2026-08-13',
    )
    expect(pick).toEqual({
      reference_number: 'CSR-2026-0001',
      title: 'Legal register (ISO 9001 6.1.3)',
      owner_name: 'Alex Owner',
      next_due_date: '2026-09-01',
      days_remaining: 19,
      status: 'current',
      notify_band: 'due_30',
    })
  })

  it('returns null when no Schedule row mentions the clause', () => {
    expect(pickSoonestMatchingObligation([unrelated], '6.1.3', '2026-08-13')).toBeNull()
  })

  it('treats a blank owner_name as unassigned rather than a fake name', () => {
    const pick = pickSoonestMatchingObligation(
      [{ ...iso9001Legal, owner_name: '  ' }],
      '6.1.3',
      '2026-08-13',
    )
    expect(pick?.owner_name).toBeNull()
  })
})
