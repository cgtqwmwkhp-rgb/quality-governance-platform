import { describe, expect, it } from 'vitest'
import { REGISTER_CATALOGUE } from '../../../data/registerCatalogue'
import {
  assertRegisterCatalogueIntegrity,
  catalogueHasRecordCounts,
  isLinkableRegister,
} from '../registerCatalogueHonesty'

describe('register catalogue honesty', () => {
  it('holds 56 unique PEL refs with 9 live spines and the 5062 hub', () => {
    expect(assertRegisterCatalogueIntegrity()).toEqual([])
    expect(REGISTER_CATALOGUE).toHaveLength(56)
  })

  it('never exposes a record count', () => {
    expect(catalogueHasRecordCounts()).toBe(false)
  })

  it('links only live, caption, and hub rows', () => {
    for (const entry of REGISTER_CATALOGUE) {
      if (entry.band === 'document' || entry.band === 'absent') {
        expect(isLinkableRegister(entry)).toBe(false)
        expect(entry.to).toBeUndefined()
      }
      if (entry.band === 'live' || entry.band === 'caption' || entry.band === 'hub') {
        expect(isLinkableRegister(entry)).toBe(true)
      }
    }
  })

  it('appends register= on incident caption hrefs without inventing a type', () => {
    const riddor = REGISTER_CATALOGUE.find((e) => e.docRef === 'PEL-HSEQ-5033')
    expect(riddor?.captionQuery).toBe('register=PEL-HSEQ-5033')
    expect(riddor?.captionQuery).not.toMatch(/type=/)
  })
})
