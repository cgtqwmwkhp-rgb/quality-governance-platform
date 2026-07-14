import { describe, expect, it } from 'vitest'
import { resolveRtaDetailTab, rtaStandardsHref } from '../rtaStandardsTab'

describe('resolveRtaDetailTab', () => {
  it('opens Standards when tab=standards (Near Miss panel parity deeplink)', () => {
    expect(resolveRtaDetailTab('standards')).toBe('standards')
  })

  it('falls back to overview for missing or unknown tabs', () => {
    expect(resolveRtaDetailTab(null)).toBe('overview')
    expect(resolveRtaDetailTab('nope')).toBe('overview')
  })

  it('accepts other known RTA tabs', () => {
    expect(resolveRtaDetailTab('actions')).toBe('actions')
    expect(resolveRtaDetailTab('photos')).toBe('photos')
  })
})

describe('rtaStandardsHref', () => {
  it('targets Standards tab like Near Miss Exceptions deep links', () => {
    expect(rtaStandardsHref(42)).toBe('/rtas/42?tab=standards')
  })
})
