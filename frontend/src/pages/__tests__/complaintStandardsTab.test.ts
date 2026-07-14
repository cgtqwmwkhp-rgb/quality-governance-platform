import { describe, expect, it } from 'vitest'
import {
  complaintStandardsHref,
  resolveComplaintDetailTab,
} from '../complaintStandardsTab'

describe('resolveComplaintDetailTab', () => {
  it('opens Standards when tab=standards (Near Miss panel parity deeplink)', () => {
    expect(resolveComplaintDetailTab('standards')).toBe('standards')
  })

  it('falls back to overview for missing or unknown tabs', () => {
    expect(resolveComplaintDetailTab(null)).toBe('overview')
    expect(resolveComplaintDetailTab(undefined)).toBe('overview')
    expect(resolveComplaintDetailTab('nope')).toBe('overview')
  })

  it('accepts other known complaint tabs', () => {
    expect(resolveComplaintDetailTab('submission')).toBe('submission')
    expect(resolveComplaintDetailTab('running-sheet')).toBe('running-sheet')
  })
})

describe('complaintStandardsHref', () => {
  it('targets Standards tab like Near Miss Exceptions deep links', () => {
    expect(complaintStandardsHref(15)).toBe('/complaints/15?tab=standards')
  })
})
