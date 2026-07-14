import { describe, expect, it } from 'vitest'
import { canOfferStaffDeepLink, portalStaffRecordLabel, portalTriageRoutedHint } from '../portalSubmitSuccess'

describe('portalSubmitSuccess', () => {
  it('offers staff deep-link only when role allows and href present', () => {
    expect(
      canOfferStaffDeepLink({
        reference_number: 'NM-1',
        can_open_staff_record: true,
        staff_href: '/near-misses/9',
      }),
    ).toBe(true)
    expect(
      canOfferStaffDeepLink({
        reference_number: 'NM-1',
        can_open_staff_record: false,
        staff_href: '/near-misses/9',
      }),
    ).toBe(false)
    expect(
      canOfferStaffDeepLink({
        reference_number: 'NM-1',
        can_open_staff_record: true,
        staff_href: null,
      }),
    ).toBe(false)
  })

  it('labels staff CTA by entity type', () => {
    expect(portalStaffRecordLabel('near_miss')).toBe('Open near-miss record')
    expect(portalStaffRecordLabel('incident')).toBe('Open incident record')
  })

  it('shows triage routed hint only when server assigned owner', () => {
    expect(portalTriageRoutedHint({ reference_number: 'INC-1', triage_assigned: true })).toContain(
      'routed to a case owner',
    )
    expect(portalTriageRoutedHint({ reference_number: 'INC-1', triage_assigned: false })).toBeNull()
  })
})
