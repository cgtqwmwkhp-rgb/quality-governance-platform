import { describe, expect, it } from 'vitest'
import { CERT_EXPIRY_WINDOW_DAYS, summariseCertificateShelf } from '../complianceAutomationHelpers'

describe('summariseCertificateShelf (PX-236)', () => {
  it('reports empty shelf as tracked 0', () => {
    expect(summariseCertificateShelf([])).toEqual({ tracked: 0, expiringSoon: 0, expired: 0 })
  })

  it('counts expiring_soon within the aligned window', () => {
    expect(CERT_EXPIRY_WINDOW_DAYS).toBe(30)
    const now = new Date('2026-07-26T00:00:00Z')
    const shelf = summariseCertificateShelf(
      [
        { expiry_date: '2026-08-10', status: 'valid' },
        { expiry_date: '2026-06-01', status: 'expired' },
        { expiry_date: null, status: 'valid' },
      ],
      now,
    )
    expect(shelf.tracked).toBe(3)
    expect(shelf.expiringSoon).toBe(1)
    expect(shelf.expired).toBe(1)
  })
})
