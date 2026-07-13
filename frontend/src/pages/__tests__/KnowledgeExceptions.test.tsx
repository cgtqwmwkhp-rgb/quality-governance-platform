import { describe, expect, it } from 'vitest'
import { exceptionEntityHref } from '../KnowledgeExceptions'

describe('exceptionEntityHref', () => {
  it('deep-links documents to Standards & Evidence tab', () => {
    expect(exceptionEntityHref('document', '42')).toBe('/documents/42?tab=evidence')
  })

  it('maps operational entity types to detail routes', () => {
    expect(exceptionEntityHref('incident', '7')).toBe('/incidents/7')
    expect(exceptionEntityHref('complaint', '3')).toBe('/complaints/3')
    expect(exceptionEntityHref('near_miss', '9')).toBe('/near-misses/9')
    expect(exceptionEntityHref('rta', '5')).toBe('/rtas/5')
    expect(exceptionEntityHref('audit_finding', '11')).toBe(
      '/audits?view=findings&findingId=11',
    )
  })

  it('returns null for unknown types or empty id', () => {
    expect(exceptionEntityHref('policy', '1')).toBeNull()
    expect(exceptionEntityHref('incident', '')).toBeNull()
  })
})
