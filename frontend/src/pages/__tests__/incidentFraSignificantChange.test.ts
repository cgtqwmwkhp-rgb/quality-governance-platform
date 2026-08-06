import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearFraSignificantChangeDismiss,
  dismissFraSignificantChange,
  incidentSuggestsFraSignificantChange,
  isFraSignificantChangeDismissed,
  shouldShowFraSignificantChangePrompt,
} from '../incidentFraSignificantChange'
import { fraSigChangeCopy } from '../incidentFraSignificantChangeI18n'

describe('incidentSuggestsFraSignificantChange', () => {
  it('is true when fire emergency services attended', () => {
    expect(
      incidentSuggestsFraSignificantChange({
        emergency_services: ['police', 'fire'],
        incident_type: 'injury',
        severity: 'low',
      }),
    ).toBe(true)
  })

  it('is true for high/critical property damage or hazard', () => {
    expect(
      incidentSuggestsFraSignificantChange({
        emergency_services: [],
        incident_type: 'property_damage',
        severity: 'high',
      }),
    ).toBe(true)
    expect(
      incidentSuggestsFraSignificantChange({
        emergency_services: [],
        incident_type: 'hazard',
        severity: 'critical',
      }),
    ).toBe(true)
  })

  it('is true for sif / psif', () => {
    expect(
      incidentSuggestsFraSignificantChange({
        emergency_services: [],
        incident_type: 'injury',
        severity: 'low',
        is_sif: true,
      }),
    ).toBe(true)
    expect(
      incidentSuggestsFraSignificantChange({
        emergency_services: [],
        incident_type: 'injury',
        severity: 'low',
        is_psif: true,
      }),
    ).toBe(true)
  })

  it('is false for low-severity injury without fire', () => {
    expect(
      incidentSuggestsFraSignificantChange({
        emergency_services: ['ambulance'],
        incident_type: 'injury',
        severity: 'low',
        is_sif: false,
        is_psif: false,
      }),
    ).toBe(false)
  })
})

describe('shouldShowFraSignificantChangePrompt', () => {
  beforeEach(() => {
    clearFraSignificantChangeDismiss(12)
  })

  it('requires flag, closed status, eligibility, and not dismissed', () => {
    const incident = {
      id: 12,
      status: 'closed',
      emergency_services: ['fire'],
      incident_type: 'injury',
      severity: 'low',
    }
    expect(shouldShowFraSignificantChangePrompt(incident, { flagEnabled: false })).toBe(false)
    expect(
      shouldShowFraSignificantChangePrompt(
        { ...incident, status: 'reported' },
        { flagEnabled: true },
      ),
    ).toBe(false)
    expect(shouldShowFraSignificantChangePrompt(incident, { flagEnabled: true })).toBe(true)

    dismissFraSignificantChange(12)
    expect(isFraSignificantChangeDismissed(12)).toBe(true)
    expect(shouldShowFraSignificantChangePrompt(incident, { flagEnabled: true })).toBe(false)
  })
})

describe('fraSigChangeCopy', () => {
  it('returns Welsh when language starts with cy', () => {
    expect(fraSigChangeCopy('cy').createFra).toContain('Creu')
    expect(fraSigChangeCopy('en').createFra).toBe('Create FRA')
  })
})
