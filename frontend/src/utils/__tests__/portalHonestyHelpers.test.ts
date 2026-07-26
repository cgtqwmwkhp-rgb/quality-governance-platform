import { describe, expect, it } from 'vitest'
import {
  countOpenAssignedActions,
  formatPortalDate,
  formatPortalReportTitle,
  humanizeCustomerCode,
} from '../portalHonestyHelpers'

describe('portalHonestyHelpers', () => {
  it('humanizes known and generic customer slugs (PX-299)', () => {
    expect(humanizeCustomerCode('plantexpand_ltd')).toBe('Plantexpand Ltd')
    expect(humanizeCustomerCode('ukpn')).toBe('UK Power Networks')
    expect(humanizeCustomerCode('thames_water')).toBe('Thames Water')
  })

  it('rewrites generic report titles with slug suffixes (PX-318)', () => {
    expect(formatPortalReportTitle('Near Miss - plantexpand_ltd')).toBe('Near Miss - Plantexpand Ltd')
    expect(formatPortalReportTitle('TEST-UAT hose burst')).toBe('TEST-UAT hose burst')
  })

  it('formats portal dates as en-GB numeric (PX-317)', () => {
    expect(formatPortalDate('2026-07-25T12:00:00Z')).toMatch(/25\/07\/2026/)
  })

  it('counts open assigned actions for hub badge (PX-305)', () => {
    expect(
      countOpenAssignedActions([
        { status: 'open' },
        { status: 'completed' },
        { display_status: 'closed' },
      ]),
    ).toBe(1)
  })
})
