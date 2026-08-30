import { describe, expect, it } from 'vitest'
import { REGISTER_CATALOGUE } from '../../../data/registerCatalogue'
import {
  assertRegisterCatalogueIntegrity,
  catalogueHasRecordCounts,
  hubOpenKind,
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

  it('captions the legal register with a statutory server filter', () => {
    const legal = REGISTER_CATALOGUE.find((e) => e.docRef === 'PEL-HSEQ-5056')
    expect(legal?.captionQuery).toBe('register=PEL-HSEQ-5056&statutory=true')
    expect(legal?.to).toBe('/compliance-schedule')
  })

  it('does not link schedule tiles when the schedule flag is off', () => {
    const legal = REGISTER_CATALOGUE.find((e) => e.docRef === 'PEL-HSEQ-5056')
    expect(legal).toBeDefined()
    expect(hubOpenKind(legal!, { compliance_schedule: false })).toBe('schedule-off')
    expect(hubOpenKind(legal!, { compliance_schedule: true })).toBe('link')
  })

  it('captions every Open except the hub (REG-SSOT-A2 includes safety-assets)', () => {
    const missing: string[] = []
    const unexpected: string[] = []
    for (const entry of REGISTER_CATALOGUE) {
      if (!entry.to) continue
      if (entry.to === '/registers') {
        if (entry.captionQuery) unexpected.push(entry.docRef)
        continue
      }
      if (!entry.captionQuery?.includes(`register=${entry.docRef}`)) {
        missing.push(entry.docRef)
      }
    }
    expect(missing).toEqual([])
    expect(unexpected).toEqual([])
  })
})
