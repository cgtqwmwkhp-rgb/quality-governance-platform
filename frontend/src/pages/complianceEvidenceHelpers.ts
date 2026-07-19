import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, BookOpen, ClipboardCheck, FileText } from 'lucide-react'

export type ComplianceEvidenceSectionId = 'clauses' | 'evidence' | 'gaps' | 'imported'

export const COMPLIANCE_EVIDENCE_SECTION_IDS: ComplianceEvidenceSectionId[] = [
  'clauses',
  'evidence',
  'gaps',
  'imported',
]

export const COMPLIANCE_EVIDENCE_DEFAULT_SECTION: ComplianceEvidenceSectionId = 'clauses'

export interface ComplianceEvidenceSectionDef {
  id: ComplianceEvidenceSectionId
  labelKey: string
  icon: LucideIcon
}

export const COMPLIANCE_EVIDENCE_SECTIONS: ComplianceEvidenceSectionDef[] = [
  { id: 'clauses', labelKey: 'compliance.evidence.shell.section.clauses', icon: BookOpen },
  { id: 'evidence', labelKey: 'compliance.evidence.shell.section.evidence', icon: FileText },
  { id: 'gaps', labelKey: 'compliance.evidence.shell.section.gaps', icon: AlertTriangle },
  { id: 'imported', labelKey: 'compliance.evidence.shell.section.imported', icon: ClipboardCheck },
]

export function parseComplianceEvidenceSection(
  value: string | null,
): ComplianceEvidenceSectionId {
  if (
    value &&
    COMPLIANCE_EVIDENCE_SECTION_IDS.includes(value as ComplianceEvidenceSectionId)
  ) {
    return value as ComplianceEvidenceSectionId
  }
  return COMPLIANCE_EVIDENCE_DEFAULT_SECTION
}

export function complianceEvidenceSectionQueryValue(
  section: ComplianceEvidenceSectionId,
): string | null {
  return section === COMPLIANCE_EVIDENCE_DEFAULT_SECTION ? null : section
}
