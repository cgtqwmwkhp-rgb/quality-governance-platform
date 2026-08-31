import { describe, expect, it } from 'vitest'
import { REGISTER_CATALOGUE } from '../../../data/registerCatalogue'
import { REGISTER_EXPORT_OVERLAYS, resolveRegisterExport } from '../registerExportOverlay'

const entry = (docRef: string) => {
  const found = REGISTER_CATALOGUE.find((row) => row.docRef === docRef)
  if (!found) throw new Error(`${docRef} missing from the catalogue`)
  return found
}

describe('registerExportOverlay', () => {
  it('offers an export only where the register is the whole module (REG-SSOT-E1)', () => {
    expect(REGISTER_EXPORT_OVERLAYS).toEqual([
      { docRef: 'PEL-HSEQ-5010', module: 'incidents' },
      { docRef: 'PEL-HSEQ-5021', module: 'risks' },
      { docRef: 'PEL-HSEQ-5059', module: 'actions' },
      { docRef: 'PEL-HSEQ-5060', module: 'complaints' },
    ])
  })

  it('names the Export Center module label for a live register', () => {
    expect(resolveRegisterExport(entry('PEL-HSEQ-5060'))).toEqual({
      module: 'complaints',
      moduleLabel: 'Complaints',
    })
  })

  it.each([
    ['PEL-HSEQ-5032', 'Accident Book — subset of incidents plus a paper book'],
    ['PEL-HSEQ-5033', 'RIDDOR — subset of incidents with no server filter to match'],
    ['PEL-PROC-5014', 'modern slavery tracker — subset of the actions module'],
    ['PEL-HSEQ-5002', 'legacy NC log — superseded alias of the actions module'],
    ['PEL-IT-5040', 'ISO 27001 2025 plan — subset of audits, IT Desk is the SoR'],
    ['PEL-HSEQ-5051', 'fire safety log — one clock inside the compliance schedule'],
    ['PEL-HSEQ-5056', 'legal register — statutory=true filter the export cannot apply'],
  ])('refuses to tag a whole-module export as %s', (docRef) => {
    expect(resolveRegisterExport(entry(docRef))).toBeUndefined()
  })

  it('refuses registers whose route has no Export Center module', () => {
    expect(resolveRegisterExport(entry('PEL-HSEQ-5013'))).toBeUndefined()
    expect(resolveRegisterExport(entry('PEL-HSEQ-5045'))).toBeUndefined()
  })

  it('refuses a live register that depends on an external system of record', () => {
    expect(entry('PEL-IT-5003').band).toBe('live')
    expect(entry('PEL-IT-5003').externalSor).toBe('IT Desk')
    expect(resolveRegisterExport(entry('PEL-IT-5003'))).toBeUndefined()
  })
})
