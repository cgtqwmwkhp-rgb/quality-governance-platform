/** Pure helpers for Compliance Automation / Monitoring page — exported for unit tests. */

import type { AuditRun } from '../api/client'

export type MonitoringAuditRunStatus = 'scheduled' | 'overdue' | 'in_progress'

export interface MonitoringAuditRunRow {
  id: number
  title: string
  referenceNumber: string
  dueDate: string | null
  status: MonitoringAuditRunStatus
  assuranceScheme?: string
  location?: string
  workspacePath: string
}

/** Authoritative Audits module entry for schedule / board handoff (CA-W1b). */
export const MONITORING_AUDITS_HANDOFF_PATH = '/audits?view=kanban'

export function isExternalAuditImportRun(run: {
  is_external_audit_import?: boolean
  is_external_import_intake?: boolean
}): boolean {
  return run.is_external_audit_import === true || run.is_external_import_intake === true
}

/** Deep-link to audit workspace — mirrors Audits.tsx without importing that page. */
export function buildAuditRunWorkspacePath(run: {
  id: number
  is_external_audit_import?: boolean
  is_external_import_intake?: boolean
}): string {
  if (!isExternalAuditImportRun(run)) {
    return `/audits/${run.id}/execute`
  }
  return `/audits/${run.id}/import-review`
}

export function deriveMonitoringAuditRunStatus(
  run: Pick<AuditRun, 'status' | 'scheduled_date' | 'due_date'>,
  now: Date = new Date(),
): MonitoringAuditRunStatus | null {
  if (run.status === 'in_progress') return 'in_progress'
  if (run.status !== 'scheduled') return null

  const due = run.scheduled_date ?? run.due_date
  if (due) {
    const dueDate = new Date(due)
    if (!Number.isNaN(dueDate.getTime()) && dueDate < now) return 'overdue'
  }
  return 'scheduled'
}

/** Map authoritative audit runs to Monitoring scheduled-audits rows (de-dupes legacy schedule API). */
export function mapRunsToMonitoringRows(
  runs: AuditRun[],
  now: Date = new Date(),
): MonitoringAuditRunRow[] {
  const rows: MonitoringAuditRunRow[] = []
  for (const run of runs) {
    const status = deriveMonitoringAuditRunStatus(run, now)
    if (!status) continue
    rows.push({
      id: run.id,
      title: run.title?.trim() || run.reference_number,
      referenceNumber: run.reference_number,
      dueDate: run.scheduled_date ?? run.due_date ?? null,
      status,
      assuranceScheme: run.assurance_scheme,
      location: run.location,
      workspacePath: buildAuditRunWorkspacePath(run),
    })
  }
  return rows.sort((a, b) => {
    const aTime = a.dueDate ? new Date(a.dueDate).getTime() : Number.POSITIVE_INFINITY
    const bTime = b.dueDate ? new Date(b.dueDate).getTime() : Number.POSITIVE_INFINITY
    return aTime - bTime
  })
}

export function countOverdueMonitoringRuns(rows: MonitoringAuditRunRow[]): number {
  return rows.filter((row) => row.status === 'overdue').length
}

export function formatStandardCode(code: string): string {
  const labels: Record<string, string> = {
    ISO9001: 'ISO 9001',
    ISO14001: 'ISO 14001',
    ISO45001: 'ISO 45001',
    ISO27001: 'ISO 27001',
  }
  return labels[code] ?? code.replace(/([A-Z]+)(\d+)/, '$1 $2')
}

export function scoreBarColor(score: number): string {
  if (score >= 80) return 'bg-success'
  if (score >= 60) return 'bg-info'
  return 'bg-primary'
}
