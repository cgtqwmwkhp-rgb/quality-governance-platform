import { describe, expect, it } from 'vitest'
import en from '../../i18n/locales/en.json'
import cy from '../../i18n/locales/cy.json'
import { statusLabel } from '../complianceScheduleHelpers'

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
