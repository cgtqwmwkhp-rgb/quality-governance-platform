import { describe, expect, it } from 'vitest'
import { portalRtaCanProceed } from '../PortalRTAForm'

const step5Base = {
  employeeName: 'Alex Engineer',
  employeeEngineerId: null,
  peVehicle: 'HV72ZUA',
  peVehicleOther: '',
  hasPassengers: false,
  passengerDetails: '',
  driverInjured: false,
  driverInjuryDetails: '',
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
  it('requires a witness answer before leaving step 3 (PX-280)', () => {
    expect(portalRtaCanProceed(3, { ...step5Base, hasWitnesses: null })).toBe(false)
    expect(portalRtaCanProceed(3, { ...step5Base, hasWitnesses: false })).toBe(true)
  })

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

  it('requires an injury answer before leaving step 1', () => {
    // An unanswered injury question was persisted as "nobody was hurt", which
    // would hide a RIDDOR-reportable collision.
    expect(portalRtaCanProceed(1, { ...step5Base, driverInjured: null })).toBe(false)
    expect(portalRtaCanProceed(1, { ...step5Base, driverInjured: false })).toBe(true)
    expect(portalRtaCanProceed(1, { ...step5Base, driverInjured: true })).toBe(true)
  })
})
