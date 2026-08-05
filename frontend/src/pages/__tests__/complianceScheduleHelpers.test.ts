import { describe, expect, it } from 'vitest'
import en from '../../i18n/locales/en.json'
import cy from '../../i18n/locales/cy.json'
import {
  anchorHint,
  anchorLabel,
  frequencyLabel,
  ownershipOf,
  statusLabel,
} from '../complianceScheduleHelpers'

describe('Compliance Schedule copy', () => {
  it('never uses Expired in en/cy schedule keys', () => {
    for (const [locale, data] of [
      ['en', en],
      ['cy', cy],
    ] as const) {
      const scheduleEntries = Object.entries(data as Record<string, string>).filter(([k]) =>
        k.startsWith('compliance.schedule'),
      )
      expect(scheduleEntries.length).toBeGreaterThan(0)
      for (const [key, value] of scheduleEntries) {
        expect(value, `${locale}:${key}`).not.toMatch(/Expired/i)
      }
    }
  })

  it('status chips are Current / Due soon / Overdue only', () => {
    expect(statusLabel('current')).toBe('Current')
    expect(statusLabel('due_soon')).toBe('Due soon')
    expect(statusLabel('overdue')).toBe('Overdue')
    expect(statusLabel(null)).toBe('—')
  })
})

describe('ownershipOf', () => {
  it('reports an obligation owned by the signed-in user as theirs', () => {
    expect(ownershipOf(42, 42)).toBe('you')
  })

  it('reports someone else’s obligation as another user’s', () => {
    expect(ownershipOf(43, 42)).toBe('other')
  })

  it('reports an unowned obligation as unassigned', () => {
    expect(ownershipOf(null, 42)).toBe('unassigned')
    expect(ownershipOf(undefined, 42)).toBe('unassigned')
  })

  it('never claims an obligation is yours when the caller is unidentifiable', () => {
    // A null current user means "we do not know who you are", which must not
    // collapse into a match against an owner id of null or 0.
    expect(ownershipOf(42, null)).toBe('other')
    expect(ownershipOf(0, null)).toBe('other')
    expect(ownershipOf(null, null)).toBe('unassigned')
  })

  it('does not treat owner 0 as unowned', () => {
    expect(ownershipOf(0, 0)).toBe('you')
  })
})

describe('frequencyLabel', () => {
  it('reports a month interval', () => {
    expect(frequencyLabel(12, null)).toBe('Every 12 months')
    expect(frequencyLabel(1, null)).toBe('Every 1 month')
  })

  it('reports a day interval', () => {
    expect(frequencyLabel(null, 30)).toBe('Every 30 days')
    expect(frequencyLabel(null, 1)).toBe('Every 1 day')
  })

  it('reports both intervals when both are set, because the scheduler adds them', () => {
    // compute_next_due adds the months first and then the days, so reporting
    // only the months would understate the real gap between occurrences.
    expect(frequencyLabel(6, 15)).toBe('Every 6 months and 15 days')
    expect(frequencyLabel(1, 1)).toBe('Every 1 month and 1 day')
  })

  it('returns null when no interval is recorded, rather than inventing one', () => {
    expect(frequencyLabel(null, null)).toBeNull()
    expect(frequencyLabel(undefined, undefined)).toBeNull()
  })

  it('treats zero and negative intervals as absent', () => {
    // The API enforces ge=1, so these only arrive from bad data. Rendering
    // "Every 0 months" would be worse than admitting there is no interval.
    expect(frequencyLabel(0, 0)).toBeNull()
    expect(frequencyLabel(-3, null)).toBeNull()
    expect(frequencyLabel(0, 14)).toBe('Every 14 days')
  })
})

describe('anchorLabel', () => {
  it('translates the stored anchor into which date the next one is measured from', () => {
    expect(anchorLabel('schedule')).toBe('Fixed schedule')
    expect(anchorLabel('completion')).toBe('From completion')
  })

  it('falls back to an em dash for an unset anchor', () => {
    expect(anchorLabel(null)).toBe('—')
    expect(anchorLabel(undefined)).toBe('—')
  })

  it('explains each anchor, and explains nothing when there is no anchor', () => {
    expect(anchorHint('schedule')).toMatch(/current due date/)
    expect(anchorHint('completion')).toMatch(/day the work is done/)
    expect(anchorHint(null)).toBeNull()
  })
})
