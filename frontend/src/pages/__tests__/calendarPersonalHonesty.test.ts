import { describe, expect, it } from 'vitest'
import {
  CAL_PERSONAL_CAPABILITIES,
  buildCalendarPersonalHonestyViewModel,
} from '../calendarPersonalHonesty'

describe('calendarPersonalHonesty', () => {
  it('lists governance feed plus personal-product capabilities', () => {
    expect(CAL_PERSONAL_CAPABILITIES).toEqual([
      'governance_feed',
      'source_create',
      'personal_events',
      'ics_sync',
      'rooms',
    ])
  })

  it('keeps personal product offline while feed create paths stay live', () => {
    const vm = buildCalendarPersonalHonestyViewModel()
    expect(vm.personalProductLive).toBe(false)
    expect(vm.capabilities.filter((c) => c.status === 'live').map((c) => c.id)).toEqual([
      'governance_feed',
      'source_create',
    ])
    expect(vm.capabilities.filter((c) => c.status === 'awaiting').map((c) => c.id)).toEqual([
      'personal_events',
      'ics_sync',
      'rooms',
    ])
  })
})
