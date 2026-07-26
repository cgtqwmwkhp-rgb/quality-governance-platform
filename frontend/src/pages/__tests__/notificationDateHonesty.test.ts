import { describe, expect, it } from 'vitest'
import {
  formatNotificationListDate,
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
