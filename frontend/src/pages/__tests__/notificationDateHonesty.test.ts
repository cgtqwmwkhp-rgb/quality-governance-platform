import { describe, expect, it } from 'vitest'
import {
  formatNotificationDisplayText,
  formatNotificationEntityLabel,
  formatNotificationListDate,
  rewriteAcronymsInNotificationText,
  rewriteIsoDatesInNotificationText,
} from '../notificationDateHonesty'

describe('notificationDateHonesty (PX-187)', () => {
  it('rewrites bare ISO dates in notification copy to UK DD/MM/YYYY', () => {
    expect(rewriteIsoDatesInNotificationText('Complete reading by 2026-08-02')).toBe(
      'Complete reading by 02/08/2026',
    )
  })

  it('leaves non-date text alone', () => {
    expect(rewriteIsoDatesInNotificationText('Requires attention.')).toBe('Requires attention.')
  })

  it('formats list stamps with the shared UK formatter', () => {
    expect(formatNotificationListDate('2026-08-02')).toBe('02/08/2026')
  })
})

describe('notificationDateHonesty (PX-188)', () => {
  it('uppercases RTA in assignment titles', () => {
    expect(rewriteAcronymsInNotificationText('New rta assigned to you')).toBe(
      'New RTA assigned to you',
    )
  })

  it('uppercases RTA when title-cased incorrectly as Rta', () => {
    expect(rewriteAcronymsInNotificationText('New Rta assigned to you')).toBe(
      'New RTA assigned to you',
    )
  })

  it('leaves ordinary words alone', () => {
    expect(rewriteAcronymsInNotificationText('High Priority Incident Reported')).toBe(
      'High Priority Incident Reported',
    )
  })

  it('formats entity chips as RTA not Rta', () => {
    expect(formatNotificationEntityLabel('rta')).toBe('RTA')
    expect(formatNotificationEntityLabel('near_miss')).toBe('Near miss')
  })

  it('applies date and acronym rewrites together', () => {
    expect(formatNotificationDisplayText('New rta due by 2026-08-02')).toBe(
      'New RTA due by 02/08/2026',
    )
  })
})
