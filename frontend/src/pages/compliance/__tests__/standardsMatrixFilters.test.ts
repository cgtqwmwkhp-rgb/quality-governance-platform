import { describe, expect, it } from 'vitest'
import {
  chunkClausesForRequest,
  filterClauseCatalogueRows,
  schemeAxisCatalogueRows,
  cellIsInteractive,
  frameworkIdFromCode,
  frameworkIdFromCode,
  MATRIX_CELL_REQUEST_LIMIT,
  parseComplianceShellView,
  resolvePresetFrameworks,
  STANDARDS_MATRIX_FRAMEWORKS,
  visibleFrameworks,
  complianceStandardIdFromFrameworkId,
  SPECIALIST_FRAMEWORK_ROUTES,
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
    const iso27001 = STANDARDS_MATRIX_FRAMEWORKS.find((f) => f.id === '27001')
    // Pinned to the ISO/IEC 27001:2022 catalogue record, not the bare-number alias.
    expect(iso27001?.homeUrl).toBe('https://www.iso.org/standard/82875.html')
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

  it('keeps CE scheme-axis rows in a separate band and only CE/CEP clickable', () => {
    const source = [
      { id: 'iso', kind: 'standard', clauseNumber: '7.2' },
      {
        id: 'ce-fw',
        kind: 'scheme',
        clauseNumber: 'firewalls',
        axisFrameworks: ['ce', 'cep'],
      },
      { id: 'uvdb-shell', kind: 'scheme', frameworkId: 'uvdb' as const, clauseNumber: 'UVDB' },
    ]
    expect(filterClauseCatalogueRows(source).map((r) => r.id)).toEqual(['iso'])
    expect(schemeAxisCatalogueRows(source).map((r) => r.id)).toEqual(['ce-fw'])
    const ceRow = schemeAxisCatalogueRows(source)[0]
    expect(cellIsInteractive(ceRow, 'ce')).toBe(true)
    expect(cellIsInteractive(ceRow, 'cep')).toBe(true)
    expect(cellIsInteractive(ceRow, '9001')).toBe(false)
    expect(cellIsInteractive(source[0], 'chas')).toBe(true)
  })

  it('resolves presets and column intersections', () => {
    expect(resolvePresetFrameworks('core')).toEqual(['9001', '14001', '45001'])
    expect(resolvePresetFrameworks('iso')).toEqual(['9001', '14001', '45001', '27001', '22301'])
    expect(resolvePresetFrameworks('environment')).toEqual(['14001', 'pm'])
    expect(resolvePresetFrameworks('bcp')).toEqual(['22301'])
    expect(visibleFrameworks('cyber', null).map((f) => f.id)).toEqual([
      '27001',
      '22301',
      'ce',
      'cep',
    ])
    expect(visibleFrameworks('buyer', null).map((f) => f.id)).toEqual([
      'pm',
      'chas',
      'ssip',
      'uvdb',
    ])
    expect(visibleFrameworks('all', ['uvdb', '9001']).map((f) => f.id)).toEqual(['9001', 'uvdb'])
  })

  it('bridges framework ids to Evidence API standard ids and specialist routes', () => {
    expect(complianceStandardIdFromFrameworkId('9001')).toBe('iso9001')
    expect(complianceStandardIdFromFrameworkId('22301')).toBe('iso22301')
    expect(complianceStandardIdFromFrameworkId('ce')).toBeNull()
    expect(SPECIALIST_FRAMEWORK_ROUTES.pm).toBe('/planet-mark')
    expect(SPECIALIST_FRAMEWORK_ROUTES.uvdb).toBe('/uvdb')
  })

  it('keeps every matrix request inside the API cell cap', () => {
    // The All preset: 12 columns against the imported 32-row axis is 384 cells,
    // which fits — the old 200 ceiling is what turned an imported matrix degraded.
    const columns = STANDARDS_MATRIX_FRAMEWORKS.length
    const axis = Array.from({ length: 32 }, (_, index) => `clause-${index}`)
    expect(chunkClausesForRequest(axis, columns)).toEqual([axis])

    const longAxis = Array.from({ length: 120 }, (_, index) => `clause-${index}`)
    const chunks = chunkClausesForRequest(longAxis, columns)
    expect(chunks.length).toBeGreaterThan(1)
    expect(chunks.flat()).toEqual(longAxis)
    for (const chunk of chunks) {
      expect(chunk.length * columns).toBeLessThanOrEqual(MATRIX_CELL_REQUEST_LIMIT)
    }
  })

  it('never returns an empty request, even for absurd column counts', () => {
    expect(chunkClausesForRequest([], 12)).toEqual([])
    expect(chunkClausesForRequest(['7.2'], 0)).toEqual([['7.2']])
    expect(chunkClausesForRequest(['7.2', '7.3'], 10_000)).toEqual([['7.2'], ['7.3']])
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
