import { describe, expect, it } from 'vitest'
import {
  LOCATION_KIND_VALUES,
  isLocationKindValue,
  locationKindLabel,
} from './locationKindLabels'

describe('locationKindLabels', () => {
  const t = (key: string, fallback?: string) => fallback ?? key

  it('exposes all four backend LocationKind values including premises and office', () => {
    expect(LOCATION_KIND_VALUES).toEqual(['site', 'workshop', 'premises', 'office'])
  })

  it('labels premises and office for the create/select UI', () => {
    expect(locationKindLabel('premises', t)).toBe('Premises')
    expect(locationKindLabel('office', t)).toBe('Office')
    expect(locationKindLabel('site', t)).toBe('Site')
    expect(locationKindLabel('workshop', t)).toBe('Workshop')
  })

  it('passes through unknown kinds without inventing a label', () => {
    expect(isLocationKindValue('depot')).toBe(false)
    expect(locationKindLabel('depot', t)).toBe('depot')
  })
})
