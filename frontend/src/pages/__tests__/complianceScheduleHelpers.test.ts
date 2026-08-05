import { describe, expect, it } from 'vitest'
import en from '../../i18n/locales/en.json'
import cy from '../../i18n/locales/cy.json'
import { ownershipOf, statusLabel } from '../complianceScheduleHelpers'

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
