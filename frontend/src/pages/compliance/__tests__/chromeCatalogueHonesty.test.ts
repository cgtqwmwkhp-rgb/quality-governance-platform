import { describe, expect, it } from 'vitest'
import {
  chromeEvidenceHonesty,
  chromeHonestyKind,
  clauseCatalogueApiFilter,
  importedRecordMatchesChrome,
  isChromeWithoutClauseCatalogue,
} from '../chromeCatalogueHonesty'

describe('chromeCatalogueHonesty', () => {
  it('treats CHAS/SSIP/PM/UVDB as chrome without a clause catalogue', () => {
    expect(isChromeWithoutClauseCatalogue('chas')).toBe(true)
    expect(isChromeWithoutClauseCatalogue('ssip')).toBe(true)
    expect(isChromeWithoutClauseCatalogue('pm')).toBe(true)
    expect(isChromeWithoutClauseCatalogue('uvdb')).toBe(true)
    expect(isChromeWithoutClauseCatalogue('iso9001')).toBe(false)
    expect(isChromeWithoutClauseCatalogue('ce')).toBe(false)
    expect(isChromeWithoutClauseCatalogue('iip')).toBe(false)
    expect(isChromeWithoutClauseCatalogue('all')).toBe(false)
  })

  it('does not send chrome ids to the clause-coverage APIs', () => {
    expect(clauseCatalogueApiFilter('all')).toBeUndefined()
    expect(clauseCatalogueApiFilter('chas')).toBeUndefined()
    expect(clauseCatalogueApiFilter('pm')).toBeUndefined()
    expect(clauseCatalogueApiFilter('iso9001')).toBe('iso9001')
    expect(clauseCatalogueApiFilter('ce')).toBe('ce')
  })

  it('names Gap Analysis as not a clause score, never zero gaps', () => {
    const gaps = chromeEvidenceHonesty('chas', 'gaps')
    expect(gaps.title).toMatch(/not a clause gap score/i)
    expect(gaps.description).toMatch(/not zero gaps/i)
    expect(chromeHonestyKind('chas')).toBe('provisional')
    expect(chromeHonestyKind('pm')).toBe('specialist')
  })

  it('matches imported records on exact scheme keys only', () => {
    expect(importedRecordMatchesChrome('planet_mark', 'pm')).toBe(true)
    expect(importedRecordMatchesChrome('Planet Mark', 'pm')).toBe(false)
    expect(importedRecordMatchesChrome('achilles_uvdb', 'uvdb')).toBe(true)
    expect(importedRecordMatchesChrome('uvdb', 'uvdb')).toBe(false)
    expect(importedRecordMatchesChrome('achilles', 'uvdb')).toBe(false)
    expect(importedRecordMatchesChrome('chas', 'chas')).toBe(true)
    expect(importedRecordMatchesChrome('ssip', 'ssip')).toBe(true)
  })
})
