import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, BookOpen, ClipboardCheck, FileText } from 'lucide-react'
import type { ClauseDocumentFreshness } from '../api/documentGraphClient'
import { documentEvidenceHref } from './documentEvidenceTab'

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

/** Deep-link from Document Detail clause chips → /compliance clause panel. */
export function complianceClauseHref(clause: string): string {
  return `/compliance?clause=${encodeURIComponent(clause)}`
}

/**
 * Entity deep-link for Linked Evidence rows.
 * When Doc Graph is on, library documents open Standards & Evidence (`?tab=evidence`).
 */
export function complianceEvidenceEntityRoute(
  entityType: string,
  entityId?: string,
  options?: { documentGraphEnabled?: boolean },
): string {
  if (entityType === 'audit_finding' && entityId) {
    return `/audits?view=findings&findingId=${encodeURIComponent(entityId)}`
  }
  if (entityType === 'audit_finding') return '/audits?view=findings'
  if (entityType === 'audit' && entityId) {
    return `/audits?runId=${encodeURIComponent(entityId)}`
  }
  if (entityType === 'action' && entityId) {
    return `/actions?sourceId=${encodeURIComponent(entityId)}`
  }
  if (entityType === 'incident' && entityId) {
    return `/incidents?id=${encodeURIComponent(entityId)}`
  }
  if (entityType === 'risk' && entityId) {
    return `/risk-register?id=${encodeURIComponent(entityId)}`
  }
  if (entityType === 'document' && entityId && options?.documentGraphEnabled) {
    return documentEvidenceHref(entityId)
  }
  if (entityType === 'document' && entityId) {
    return `/documents/${encodeURIComponent(entityId)}`
  }
  if (entityType === 'document') return '/documents'
  if (entityType === 'training') return '/workforce/training'
  if (entityType === 'policy') return '/policies'
  if (entityType === 'complaint') return '/complaints'
  if (entityType === 'near_miss') return '/near-misses'
  return `/${entityType}s`
}

export function clauseDocumentFreshnessLabel(freshness: ClauseDocumentFreshness): string {
  switch (freshness) {
    case 'current':
      return 'Current tip'
    case 'stale':
      return 'Superseded pin'
    case 'unpinned':
      return 'Version unpinned'
    case 'unknown':
      return 'Tip unknown'
    default:
      return freshness
  }
}

export function clauseDocumentFreshnessTone(
  freshness: ClauseDocumentFreshness,
): 'success' | 'warning' | 'secondary' | 'outline' {
  switch (freshness) {
    case 'current':
      return 'success'
    case 'stale':
      return 'warning'
    case 'unpinned':
      return 'secondary'
    case 'unknown':
      return 'outline'
    default:
      return 'secondary'
  }
}
