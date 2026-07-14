import { describe, expect, it } from 'vitest'
import {
  incidentStandardsHref,
  resolveIncidentDetailTab,
} from '../incidentStandardsTab'

describe('resolveIncidentDetailTab', () => {
  it('opens Standards when tab=standards (Near Miss panel parity deeplink)', () => {
    expect(resolveIncidentDetailTab('standards')).toBe('standards')
  })

  it('falls back to overview for missing or unknown tabs', () => {
    expect(resolveIncidentDetailTab(null)).toBe('overview')
    expect(resolveIncidentDetailTab('nope')).toBe('overview')
  })

  it('accepts other known incident tabs', () => {
    expect(resolveIncidentDetailTab('submission')).toBe('submission')
    expect(resolveIncidentDetailTab('running-sheet')).toBe('running-sheet')
  })
})

describe('incidentStandardsHref', () => {
  it('targets Standards tab like Near Miss Exceptions deep links', () => {
    expect(incidentStandardsHref(11)).toBe('/incidents/11?tab=standards')
  })
})
