import { describe, expect, it } from 'vitest'
import {
  LOCATION_KIND_VALUES,
  isLocationKindValue,
  locationKindI18n,
} from './locationKindLabels'

describe('locationKindLabels', () => {
  it('exposes all four backend LocationKind values including premises and office', () => {
    expect(LOCATION_KIND_VALUES).toEqual(['site', 'workshop', 'premises', 'office'])
  })

  it('returns i18n keys for premises and office', () => {
    expect(locationKindI18n('premises')).toEqual({
      key: 'admin.lookups.location_kind.premises',
      fallback: 'Premises',
    })
    expect(locationKindI18n('office').fallback).toBe('Office')
    expect(locationKindI18n('site').fallback).toBe('Site')
    expect(locationKindI18n('workshop').fallback).toBe('Workshop')
  })

  it('passes through unknown kinds without inventing a label', () => {
    expect(isLocationKindValue('depot')).toBe(false)
    expect(locationKindI18n('depot')).toEqual({ key: 'depot', fallback: 'depot' })
  })
})
