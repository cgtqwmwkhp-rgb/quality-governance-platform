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
    expect(visibleFrameworks('cyber', null).map((f) => f.id)).toEqual(['27001', '22301'])
    expect(visibleFrameworks('all', ['uvdb', '9001']).map((f) => f.id)).toEqual(['9001', 'uvdb'])
  })

  it('maps Assist codes onto framework ids', () => {
    expect(frameworkIdFromCode('ISO9001')).toBe('9001')
    expect(frameworkIdFromCode('planetmark')).toBe('pm')
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
