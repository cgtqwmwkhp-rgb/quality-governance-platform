import { describe, expect, it } from 'vitest'
import { REGISTER_CATALOGUE } from '../../../data/registerCatalogue'
import {
  assertRegisterCatalogueIntegrity,
  catalogueHasRecordCounts,
  hubOpenKind,
  isLinkableRegister,
  registerHref,
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

describe('form-engine trio (REG-SSOT-D1)', () => {
  const TRIO = ['PEL-HSEQ-5026', 'PEL-HSEQ-5036', 'PEL-HSEQ-5043'] as const

  it.each(TRIO)('%s opens the real Form Builder route, captioned', (docRef) => {
    const entry = REGISTER_CATALOGUE.find((e) => e.docRef === docRef)
    expect(entry).toBeDefined()
    expect(entry!.band).toBe('caption')
    expect(entry!.to).toBe('/admin/forms')
    expect(entry!.captionQuery).toBe(`register=${docRef}`)
    expect(registerHref(entry!)).toBe(`/admin/forms?register=${docRef}`)
    expect(hubOpenKind(entry!, { compliance_schedule: false })).toBe('link')
  })

  it.each(TRIO)('%s says plainly that no dedicated list exists', (docRef) => {
    const entry = REGISTER_CATALOGUE.find((e) => e.docRef === docRef)
    // Caption band + this note is what drives the hub EMPTY chip; without it the
    // row would imply a populated register behind the Open link.
    expect(entry!.note).toMatch(/no dedicated /i)
    expect(entry!.band).not.toBe('live')
  })

  it.each([
    ['PEL-HSEQ-5026', 'worker-consultation-record'],
    ['PEL-HSEQ-5036', 'permit-to-work-record'],
    ['PEL-HSEQ-5043', 'remote-working-record'],
  ])('%s names the seeded template slug so the Open is findable', (docRef, slug) => {
    // Slugs come from alembic/versions/20261116_seed_register_form_trio.py.
    // Rename one there without renaming it here and the Open lands on a Form
    // Builder list where nothing matches the note.
    const entry = REGISTER_CATALOGUE.find((e) => e.docRef === docRef)
    expect(entry!.note).toContain(slug)
  })

  it('does not promote the trio to a fake list route or a portal intake route', () => {
    for (const docRef of TRIO) {
      const entry = REGISTER_CATALOGUE.find((e) => e.docRef === docRef)!
      // The portal intake endpoint only accepts incident/complaint/rta/near_miss,
      // so a /portal/report/* Open for these would dead-end on submit.
      expect(entry.to).not.toMatch(/^\/portal\//)
      expect(entry.to).not.toBe('/incidents')
    }
  })

  it('leaves the locked absent rows alone', () => {
    for (const docRef of ['PEL-HSEQ-5008', 'PEL-HSEQ-5028']) {
      const entry = REGISTER_CATALOGUE.find((e) => e.docRef === docRef)
      expect(entry?.band).toBe('absent')
      expect(entry?.to).toBeUndefined()
    }
  })
})
