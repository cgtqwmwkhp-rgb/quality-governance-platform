import type { LucideIcon } from 'lucide-react'
import { AlertCircle, ClipboardList, FileText } from 'lucide-react'
import type { AuditRun } from '../api/client'
import { isCustomerAssuranceAudit } from '../components/assuranceHubHelpers'

export type CustomerAuditsSectionId = 'runs' | 'findings' | 'sources'

export const CUSTOMER_AUDITS_SECTION_IDS: CustomerAuditsSectionId[] = [
  'runs',
  'findings',
  'sources',
]

export interface CustomerAuditsSectionDef {
  id: CustomerAuditsSectionId
  labelKey: string
  icon: LucideIcon
}

export const CUSTOMER_AUDITS_SECTIONS: CustomerAuditsSectionDef[] = [
  { id: 'runs', labelKey: 'customer_audits.shell.section.runs', icon: ClipboardList },
  { id: 'findings', labelKey: 'customer_audits.shell.section.findings', icon: AlertCircle },
  { id: 'sources', labelKey: 'customer_audits.shell.section.sources', icon: FileText },
]

export function parseCustomerAuditsSection(value: string | null): CustomerAuditsSectionId {
  if (value && CUSTOMER_AUDITS_SECTION_IDS.includes(value as CustomerAuditsSectionId)) {
    return value as CustomerAuditsSectionId
  }
  return 'runs'
}

export function filterCustomerAssuranceRuns(audits: AuditRun[]): AuditRun[] {
  return audits.filter(isCustomerAssuranceAudit)
}

export function isExternalAuditImportRun(audit: AuditRun): boolean {
  return audit.is_external_audit_import === true || audit.is_external_import_intake === true
}

export function getCustomerAuditWorkspacePath(
  audit: AuditRun,
  importJobId?: number | null,
): string {
  if (!isExternalAuditImportRun(audit)) {
    return `/audits/${audit.id}/execute`
  }
  const params = importJobId ? `?jobId=${importJobId}` : ''
  return `/audits/${audit.id}/import-review${params}`
}

export function buildCustomerAuditsSummary(runs: AuditRun[], openFindings: number) {
  return {
    total: runs.length,
    inProgress: runs.filter(
      (run) => run.status === 'in_progress' || run.status === 'scheduled',
    ).length,
    completed: runs.filter((run) => run.status === 'completed').length,
    pendingReview: runs.filter((run) => run.status === 'pending_review').length,
    openFindings,
    withSourceDoc: runs.filter(
      (run) =>
        run.source_document_asset_id != null && Number(run.source_document_asset_id) > 0,
    ).length,
  }
}
