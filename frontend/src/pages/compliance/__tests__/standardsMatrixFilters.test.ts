import { describe, expect, it } from 'vitest'
import {
  filterClauseCatalogueRows,
  frameworkIdFromCode,
  parseComplianceShellView,
  resolvePresetFrameworks,
  STANDARDS_MATRIX_FRAMEWORKS,
  visibleFrameworks,
} from '../standardsMatrixFilters'

describe('standardsMatrixFilters', () => {
  it('excludes Constructionline and includes the Wave 1 framework set', () => {
    const ids = STANDARDS_MATRIX_FRAMEWORKS.map((f) => f.id)
    expect(ids).toEqual([
      '9001',
      '14001',
      '45001',
      '27001',
      '22301',
      'ce',
      'cep',
      'iip',
      'pm',
      'chas',
      'ssip',
      'uvdb',
    ])
    expect(ids).not.toContain('constructionline')
  })

  it('labels CE / CEP as Cyber Essentials with official NCSC home links', () => {
    const ce = STANDARDS_MATRIX_FRAMEWORKS.find((f) => f.id === 'ce')
    const cep = STANDARDS_MATRIX_FRAMEWORKS.find((f) => f.id === 'cep')
    expect(ce?.label).toBe('Cyber Essentials')
    expect(cep?.label).toBe('Cyber Essentials Plus')
    expect(STANDARDS_MATRIX_FRAMEWORKS.every((f) => !/carbon/i.test(f.label))).toBe(true)
    for (const fw of STANDARDS_MATRIX_FRAMEWORKS) {
      expect(fw.homeUrl.startsWith('https://')).toBe(true)
      expect(fw.homeUrl).not.toContain('?')
      expect(fw.homeUrl.toLowerCase()).not.toContain('utm_')
    }
    expect(ce?.homeUrl).toBe('https://www.ncsc.gov.uk/cyberessentials/resources')
    expect(cep?.homeUrl).toBe('https://www.ncsc.gov.uk/cyberessentials/resources')
  })

  it('quarantines scheme-kind rows from the clause catalogue', () => {
    const rows = filterClauseCatalogueRows([
      { id: '1', kind: 'standard', clauseNumber: '7.2' },
      { id: '2', kind: 'scheme', clauseNumber: 'UVDB' },
      { id: '3', clauseNumber: '4.1' },
      { id: '4', kind: 'accreditation', clauseNumber: 'CHAS-1' },
    ])
    expect(rows.map((r) => r.id)).toEqual(['1', '3', '4'])
  })

  it('resolves presets and column intersections', () => {
    expect(resolvePresetFrameworks('core')).toEqual(['9001', '14001', '45001'])
    expect(visibleFrameworks('cyber', null).map((f) => f.id)).toEqual([
      '27001',
      '22301',
      'ce',
      'cep',
    ])
    expect(visibleFrameworks('buyer', null).map((f) => f.id)).toEqual(['pm', 'uvdb'])
    expect(visibleFrameworks('all', ['uvdb', '9001']).map((f) => f.id)).toEqual(['9001', 'uvdb'])
  })

  it('maps Assist codes onto framework ids', () => {
    expect(frameworkIdFromCode('ISO9001')).toBe('9001')
    expect(frameworkIdFromCode('planetmark')).toBe('pm')
    expect(frameworkIdFromCode('Cyber Essentials')).toBe('ce')
    expect(frameworkIdFromCode('Cyber Essentials Plus')).toBe('cep')
    expect(frameworkIdFromCode('nope')).toBeNull()
  })
})

describe('parseComplianceShellView', () => {
  it('defaults to evidence for existing CUJs', () => {
    expect(parseComplianceShellView(null)).toBe('evidence')
    expect(parseComplianceShellView(null, '')).toBe('evidence')
  })

  it('honours view= and Standards code deep-links', () => {
    expect(parseComplianceShellView('matrix')).toBe('matrix')
    expect(parseComplianceShellView('evidence', 'ISO9001')).toBe('evidence')
    expect(parseComplianceShellView(null, 'ISO9001')).toBe('matrix')
  })
})
