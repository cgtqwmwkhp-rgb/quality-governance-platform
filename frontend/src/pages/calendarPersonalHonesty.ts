/** CAL personal-product honesty shell (not full Option C). */

export const CAL_PERSONAL_CAPABILITIES = [
  'governance_feed',
  'source_create',
  'personal_events',
  'ics_sync',
  'rooms',
] as const

export type CalPersonalCapability = (typeof CAL_PERSONAL_CAPABILITIES)[number]

export type CalPersonalCapabilityStatus = 'live' | 'awaiting'

export interface CalPersonalCapabilityRow {
  id: CalPersonalCapability
  status: CalPersonalCapabilityStatus
}

export interface CalPersonalHonestyViewModel {
  capabilities: CalPersonalCapabilityRow[]
  personalProductLive: boolean
}

/** Governance feed + source-module create are live; Outlook-class personal product is not. */
export function buildCalendarPersonalHonestyViewModel(): CalPersonalHonestyViewModel {
  return {
    personalProductLive: false,
    capabilities: [
      { id: 'governance_feed', status: 'live' },
      { id: 'source_create', status: 'live' },
      { id: 'personal_events', status: 'awaiting' },
      { id: 'ics_sync', status: 'awaiting' },
      { id: 'rooms', status: 'awaiting' },
    ],
  }
}
