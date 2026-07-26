import { describe, expect, it } from 'vitest'
import { portalRtaCanProceed } from '../PortalRTAForm'

const step5Base = {
  employeeName: 'Alex Engineer',
  peVehicle: 'HV72ZUA',
  peVehicleOther: '',
  hasPassengers: false,
  passengerDetails: '',
  location: 'M4 J12',
  accidentDate: '2026-07-26',
  accidentTime: '09:30',
  accidentType: 'rear-end',
  vehicleCount: 1,
  thirdParties: [],
  impactPoint: 'rear',
  damageDescription: 'Bumper dented',
  isDrivable: true,
  weather: 'clear',
  roadCondition: 'dry',
  hasWitnesses: false,
  witnessDetails: '',
  emergencyServices: '',
  policeRef: '',
  purposeOfJourney: '',
  speed: '',
  hasDashcam: false,
  hasCCTV: false,
  thirdPartyInjured: false,
  fullDescription: '',
  photos: [],
}

describe('portalRtaCanProceed — PX-277', () => {
  it('blocks step 5 when the mandatory full description is empty or whitespace', () => {
    expect(portalRtaCanProceed(5, { ...step5Base, fullDescription: '' })).toBe(false)
    expect(portalRtaCanProceed(5, { ...step5Base, fullDescription: '   ' })).toBe(false)
  })

  it('allows step 5 once the full description is supplied', () => {
    expect(
      portalRtaCanProceed(5, {
        ...step5Base,
        fullDescription: 'Rear-ended at traffic lights; third party pulled away.',
      }),
    ).toBe(true)
  })

  it('still gates earlier mandatory steps', () => {
    expect(portalRtaCanProceed(4, { ...step5Base, damageDescription: '' })).toBe(false)
    expect(portalRtaCanProceed(2, { ...step5Base, location: '' })).toBe(false)
  })
})
