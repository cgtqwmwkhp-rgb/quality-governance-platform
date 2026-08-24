import { describe, expect, it } from 'vitest'
import {
  COMPLIANCE_EVIDENCE_DEFAULT_SECTION,
  COMPLIANCE_EVIDENCE_SECTION_IDS,
  clauseDocumentFreshnessLabel,
  clauseDocumentFreshnessTone,
  complianceClauseHref,
  complianceEvidenceEntityRoute,
  complianceEvidenceSectionQueryValue,
  parseComplianceEvidenceSection,
} from '../complianceEvidenceHelpers'

describe('complianceEvidenceHelpers', () => {
  it('lists all ISO compliance shell section IDs', () => {
    expect(COMPLIANCE_EVIDENCE_SECTION_IDS).toEqual(['clauses', 'evidence', 'gaps', 'imported'])
  })

  it('parses section param with safe fallback to clauses', () => {
    expect(parseComplianceEvidenceSection(null)).toBe('clauses')
    expect(parseComplianceEvidenceSection('unknown')).toBe('clauses')
    expect(parseComplianceEvidenceSection('gaps')).toBe('gaps')
    expect(parseComplianceEvidenceSection('imported')).toBe('imported')
  })

  it('omits default section from query patch values', () => {
    expect(complianceEvidenceSectionQueryValue(COMPLIANCE_EVIDENCE_DEFAULT_SECTION)).toBeNull()
    expect(complianceEvidenceSectionQueryValue('evidence')).toBe('evidence')
  })

  it('builds /compliance?clause= deep-links', () => {
    expect(complianceClauseHref('9001-7.5')).toBe('/compliance?clause=9001-7.5')
    expect(complianceClauseHref('7.5')).toBe('/compliance?clause=7.5')
  })

  it('deep-links documents to Standards & Evidence when Doc Graph is on', () => {
    expect(
      complianceEvidenceEntityRoute('document', '42', { documentGraphEnabled: true }),
    ).toBe('/documents/42?tab=evidence')
  })

  it('keeps plain document routes when Doc Graph is off', () => {
    expect(
      complianceEvidenceEntityRoute('document', '42', { documentGraphEnabled: false }),
    ).toBe('/documents/42')
  })

  it('preserves finding and action deep-links', () => {
    expect(complianceEvidenceEntityRoute('audit_finding', '9')).toBe(
      '/audits?view=findings&findingId=9',
    )
    expect(complianceEvidenceEntityRoute('action', '3')).toBe('/actions?sourceId=3')
  })

  it('labels CEL tip freshness honestly', () => {
    expect(clauseDocumentFreshnessLabel('current')).toBe('Current tip')
    expect(clauseDocumentFreshnessLabel('stale')).toBe('Superseded pin')
    expect(clauseDocumentFreshnessLabel('unpinned')).toBe('Version unpinned')
    expect(clauseDocumentFreshnessLabel('unknown')).toBe('Tip unknown')
    expect(clauseDocumentFreshnessTone('stale')).toBe('warning')
    expect(clauseDocumentFreshnessTone('current')).toBe('success')
  })
})
