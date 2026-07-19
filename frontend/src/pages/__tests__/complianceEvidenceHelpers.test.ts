import { describe, expect, it } from 'vitest'
import {
  COMPLIANCE_EVIDENCE_DEFAULT_SECTION,
  COMPLIANCE_EVIDENCE_SECTION_IDS,
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
})
