/** Pure helpers for Compliance Automation / Monitoring page — exported for unit tests. */

import type { AuditRun } from '../api/client'
import { STANDARDS_MATRIX_FRAMEWORKS } from './compliance/standardsMatrixFilters'

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

/** Authoritative IMS multi-scheme score surface (CA-W1b Score-tab kill). */
export const MONITORING_SCORE_HANDOFF_IMS = '/ims'

/** Evidence coverage / Compliance Evidence hub (CA-W1b Score-tab kill). */
export const MONITORING_SCORE_HANDOFF_EVIDENCE = '/compliance'

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

/**
 * Monitoring handoff path: Continue in-progress runs in execute workspace;
 * scheduled/overdue open the Audits board (not a random live execute).
 */
export function buildMonitoringAuditHandoffPath(
  run: {
    id: number
    is_external_audit_import?: boolean
    is_external_import_intake?: boolean
  },
  status: MonitoringAuditRunStatus,
): string {
  if (status === 'in_progress' || isExternalAuditImportRun(run)) {
    return buildAuditRunWorkspacePath(run)
  }
  return MONITORING_AUDITS_HANDOFF_PATH
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
  return runs
    .flatMap((run) => {
      const status = deriveMonitoringAuditRunStatus(run, now)
      if (!status) return []

      const row: MonitoringAuditRunRow = {
        id: run.id,
        title: run.title?.trim() || run.reference_number,
        referenceNumber: run.reference_number,
        dueDate: run.scheduled_date ?? run.due_date ?? null,
        status,
        workspacePath: buildMonitoringAuditHandoffPath(run, status),
      }
      if (run.assurance_scheme !== undefined) {
        row.assuranceScheme = run.assurance_scheme
      }
      if (run.location !== undefined) {
        row.location = run.location
      }
      return [row]
    })
    .sort((a, b) => {
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

/** True when Monitoring has real score categories or a non-zero overall — not an empty API shell. */
export function hasLiveComplianceScore(
  overall: number,
  categories: Record<string, number> | undefined,
): boolean {
  if (Object.keys(categories ?? {}).length > 0) return true
  return overall > 0
}

/** Open regulatory-watch impact rows eligible for the Changes inbox badge. */
export function isOpenWatchImpact(impact: { status: string }): boolean {
  return impact.status !== 'resolved' && impact.status !== 'dismissed'
}

export function countUnreviewedRegulatoryUpdates(
  updates: ReadonlyArray<{ is_reviewed: boolean }>,
): number {
  return updates.filter((update) => !update.is_reviewed).length
}

export function countOpenWatchImpacts(impacts: ReadonlyArray<{ status: string }>): number {
  return impacts.filter(isOpenWatchImpact).length
}

/** Pending feed reviews + open matched impacts for the unified Changes inbox tab badge. */
export function countPendingChangesInbox(
  updates: ReadonlyArray<{ is_reviewed: boolean }>,
  impacts: ReadonlyArray<{ status: string }>,
): number {
  return countUnreviewedRegulatoryUpdates(updates) + countOpenWatchImpacts(impacts)
}

/** Persisted RIDDOR pack row from compliance-automation register (CA-W1e). */
export interface MonitoringRiddorPack {
  id: number
  incidentId: number
  incidentReference: string | null
  riddorType: string
  submissionStatus: string
  statusLabel: string
  deadline: string | null
  isOverdue: boolean
  persisted: boolean
}

export function mapRiddorSubmissionToPack(raw: Record<string, unknown>): MonitoringRiddorPack | null {
  const id = Number(raw.id)
  const incidentId = Number(raw.incident_id)
  if (!Number.isFinite(id) || !Number.isFinite(incidentId)) return null

  const status =
    typeof raw.submission_status === 'string'
      ? raw.submission_status
      : typeof raw.status === 'string'
        ? raw.status
        : 'draft_pack'

  return {
    id,
    incidentId,
    incidentReference: typeof raw.incident_reference === 'string' ? raw.incident_reference : null,
    riddorType: typeof raw.riddor_type === 'string' ? raw.riddor_type : 'unknown',
    submissionStatus: status,
    statusLabel:
      typeof raw.status_label === 'string'
        ? raw.status_label
        : 'Draft pack saved in QGP — file on the HSE portal',
    deadline: typeof raw.deadline === 'string' ? raw.deadline : null,
    isOverdue: raw.is_overdue === true,
    persisted: raw.persisted !== false,
  }
}

export function mapRiddorSubmissionsToPacks(raw: unknown): MonitoringRiddorPack[] {
  if (!Array.isArray(raw)) return []
  return raw.flatMap((row) => {
    if (!row || typeof row !== 'object') return []
    const pack = mapRiddorSubmissionToPack(row as Record<string, unknown>)
    return pack ? [pack] : []
  })
}

/** Certificate shelf expiry window used by Monitoring tiles (PX-236). */
export const CERT_EXPIRY_WINDOW_DAYS = 30

export function summariseCertificateShelf(
  certs: ReadonlyArray<{ expiry_date: string | null; status: string }>,
  now: Date = new Date(),
): { tracked: number; expiringSoon: number; expired: number } {
  const windowMs = CERT_EXPIRY_WINDOW_DAYS * 24 * 60 * 60 * 1000
  let expiringSoon = 0
  let expired = 0
  for (const cert of certs) {
    if (cert.status === 'expired') {
      expired += 1
      continue
    }
    if (cert.status === 'expiring_soon') {
      expiringSoon += 1
      continue
    }
    if (!cert.expiry_date) continue
    const expiry = new Date(cert.expiry_date)
    if (Number.isNaN(expiry.getTime())) continue
    if (expiry < now) expired += 1
    else if (expiry.getTime() - now.getTime() <= windowMs) expiringSoon += 1
  }
  return { tracked: certs.length, expiringSoon, expired }
}

// ---------------------------------------------------------------------------
// Standards health digests (Wave 3 PR-F3) — tolerant readers
// ---------------------------------------------------------------------------

export interface StandardsDigestNcRow {
  framework: string | null
  clauseNumber: string
  clauseKey: string
  openNcCount: number
  closedNcCount: number
  recurrence: boolean
  latestNcAt: string | null
  clausePath: string | null
  findingsPath: string
}

export interface StandardsDigestFreshness {
  trackedDocumentLinks: number
  current: number
  stale: number
  unpinned: number
  unknown: number
  staleRate: number | null
  scanTruncated: boolean
  staleItems: Array<{
    evidenceLinkId: number | null
    clauseId: string | null
    framework: string | null
    clauseNumber: string
    documentId: number | null
    title: string | null
    tipVersionNumber: string | null
    clausePath: string | null
    documentPath: string | null
  }>
}

export interface StandardsDigestBacklog {
  total: number
  byStatus: Record<string, number>
  byLinkMethod: Record<string, number>
  operationalSignals: number
  conformanceCandidates: number
  oldestAgeDays: number | null
  scanTruncated: boolean
  autoConfirmThreshold: number
  autoConfirmRule: string
  inboxPath: string
  byClause: Array<{
    clauseId: string
    framework: string | null
    clauseNumber: string
    count: number
    inboxPath: string
  }>
}

export interface StandardsDigestCertExpiry {
  tracked: number
  valid: number
  dueSoon: number
  expired: number
  unknown: number
  shelfPath: string
  byScheme: Array<{ scheme: string; tracked: number; dueSoon: number; expired: number }>
  soonest: Array<{
    shelfKey: string | null
    name: string
    scheme: string
    expiryDate: string | null
    readinessStatus: string
    daysRemaining: number | null
    isCritical: boolean
    detailPath: string
  }>
}

export interface StandardsDigest {
  generatedAt: string | null
  dueSoonDays: number
  freshness: StandardsDigestFreshness
  ingestBacklog: StandardsDigestBacklog
  nonconformity: {
    openNcTotal: number
    openNcWithoutClauseToken: number
    clausesWithOpenNc: number
    unattributedOpenNc: number
    recurringClauses: number
    clausesWithNcHistory: number
    recurrenceRate: number | null
    scanTruncated: boolean
    byClause: StandardsDigestNcRow[]
  }
  certExpiry: StandardsDigestCertExpiry
  sorNote: string | null
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function asNullableNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

export function formatDigestRate(rate: number | null): string {
  if (rate === null || Number.isNaN(rate)) return '—'
  return `${(rate * 100).toFixed(1)}%`
}

export function standardsDigestFrameworkLabel(framework: string | null): string {
  if (framework == null || framework === '') return 'Unattributed'
  const match = STANDARDS_MATRIX_FRAMEWORKS.find((fw) => fw.id === framework)
  return match?.label ?? framework
}

export function digestStalePinsLabel(freshness: StandardsDigestFreshness): string {
  if (freshness.trackedDocumentLinks === 0) return '—'
  return String(freshness.stale)
}

export function countStandardsDigestBacklog(digest: StandardsDigest | null): number {
  return digest?.ingestBacklog.total ?? 0
}

export function standardsDigestClauseHref(row: {
  framework: string | null
  clauseNumber: string
  clausePath?: string | null
}): string {
  if (row.clausePath) return row.clausePath
  if (row.framework && row.clauseNumber) {
    return `/compliance?code=${encodeURIComponent(row.framework)}&clause=${encodeURIComponent(row.clauseNumber)}`
  }
  return '/compliance'
}

export function mapStandardsDigest(raw: unknown): StandardsDigest | null {
  if (!raw || typeof raw !== 'object') return null
  const root = asRecord(raw)
  const freshness = asRecord(root.freshness)
  const backlog = asRecord(root.ingest_backlog)
  const nc = asRecord(root.nonconformity)
  const certs = asRecord(root.cert_expiry)

  const staleItems = Array.isArray(freshness.stale_items)
    ? freshness.stale_items.flatMap((item) => {
        if (!item || typeof item !== 'object') return []
        const row = asRecord(item)
        return [
          {
            evidenceLinkId: asNullableNumber(row.evidence_link_id),
            clauseId: typeof row.clause_id === 'string' ? row.clause_id : null,
            framework: typeof row.framework === 'string' ? row.framework : null,
            clauseNumber: asString(row.clause_number),
            documentId: asNullableNumber(row.document_id),
            title: typeof row.title === 'string' ? row.title : null,
            tipVersionNumber: typeof row.tip_version_number === 'string' ? row.tip_version_number : null,
            clausePath: typeof row.clause_path === 'string' ? row.clause_path : null,
            documentPath: typeof row.document_path === 'string' ? row.document_path : null,
          },
        ]
      })
    : []

  const ncRows: StandardsDigestNcRow[] = Array.isArray(nc.by_clause)
    ? nc.by_clause.flatMap((item) => {
        if (!item || typeof item !== 'object') return []
        const row = asRecord(item)
        return [
          {
            framework: typeof row.framework === 'string' ? row.framework : null,
            clauseNumber: asString(row.clause_number),
            clauseKey: asString(row.clause_key),
            openNcCount: asNumber(row.open_nc_count),
            closedNcCount: asNumber(row.closed_nc_count),
            recurrence: Boolean(row.recurrence),
            latestNcAt: typeof row.latest_nc_at === 'string' ? row.latest_nc_at : null,
            clausePath: typeof row.clause_path === 'string' ? row.clause_path : null,
            findingsPath: asString(row.findings_path, '/audits?view=findings'),
          },
        ]
      })
    : []

  const backlogClauses = Array.isArray(backlog.by_clause)
    ? backlog.by_clause.flatMap((item) => {
        if (!item || typeof item !== 'object') return []
        const row = asRecord(item)
        return [
          {
            clauseId: asString(row.clause_id),
            framework: typeof row.framework === 'string' ? row.framework : null,
            clauseNumber: asString(row.clause_number),
            count: asNumber(row.count),
            inboxPath: asString(row.inbox_path, '/knowledge-exceptions'),
          },
        ]
      })
    : []

  const byScheme = Array.isArray(certs.by_scheme)
    ? certs.by_scheme.flatMap((item) => {
        if (!item || typeof item !== 'object') return []
        const row = asRecord(item)
        return [
          {
            scheme: asString(row.scheme, 'unknown'),
            tracked: asNumber(row.tracked),
            dueSoon: asNumber(row.due_soon),
            expired: asNumber(row.expired),
          },
        ]
      })
    : []

  const soonest = Array.isArray(certs.soonest)
    ? certs.soonest.flatMap((item) => {
        if (!item || typeof item !== 'object') return []
        const row = asRecord(item)
        return [
          {
            shelfKey: typeof row.shelf_key === 'string' ? row.shelf_key : null,
            name: asString(row.name, 'Certificate'),
            scheme: asString(row.scheme, 'unknown'),
            expiryDate: typeof row.expiry_date === 'string' ? row.expiry_date : null,
            readinessStatus: asString(row.readiness_status, 'unknown'),
            daysRemaining: asNullableNumber(row.days_remaining),
            isCritical: Boolean(row.is_critical),
            detailPath: asString(row.detail_path, '/compliance-schedule?view=certificates'),
          },
        ]
      })
    : []

  return {
    generatedAt: typeof root.generated_at === 'string' ? root.generated_at : null,
    dueSoonDays: asNumber(root.due_soon_days, CERT_EXPIRY_WINDOW_DAYS),
    freshness: {
      trackedDocumentLinks: asNumber(freshness.tracked_document_links),
      current: asNumber(freshness.current),
      stale: asNumber(freshness.stale),
      unpinned: asNumber(freshness.unpinned),
      unknown: asNumber(freshness.unknown),
      staleRate: asNullableNumber(freshness.stale_rate),
      scanTruncated: Boolean(freshness.scan_truncated),
      staleItems,
    },
    ingestBacklog: {
      total: asNumber(backlog.total),
      byStatus: asRecord(backlog.by_status) as Record<string, number>,
      byLinkMethod: asRecord(backlog.by_link_method) as Record<string, number>,
      operationalSignals: asNumber(backlog.operational_signals),
      conformanceCandidates: asNumber(backlog.conformance_candidates),
      oldestAgeDays: asNullableNumber(backlog.oldest_age_days),
      scanTruncated: Boolean(backlog.scan_truncated),
      autoConfirmThreshold: asNumber(backlog.auto_confirm_threshold, 0.98),
      autoConfirmRule: asString(
        backlog.auto_confirm_rule,
        'Machine confirm requires confidence ≥ 0.98 and EXACT alignment.',
      ),
      inboxPath: asString(backlog.inbox_path, '/knowledge-exceptions'),
      byClause: backlogClauses,
    },
    nonconformity: {
      openNcTotal: asNumber(nc.open_nc_total),
      openNcWithoutClauseToken: asNumber(nc.open_nc_without_clause_token),
      clausesWithOpenNc: asNumber(nc.clauses_with_open_nc),
      unattributedOpenNc: asNumber(nc.unattributed_open_nc),
      recurringClauses: asNumber(nc.recurring_clauses),
      clausesWithNcHistory: asNumber(nc.clauses_with_nc_history),
      recurrenceRate: asNullableNumber(nc.recurrence_rate),
      scanTruncated: Boolean(nc.scan_truncated),
      byClause: ncRows,
    },
    certExpiry: {
      tracked: asNumber(certs.tracked),
      valid: asNumber(certs.valid),
      dueSoon: asNumber(certs.due_soon),
      expired: asNumber(certs.expired),
      unknown: asNumber(certs.unknown),
      shelfPath: asString(certs.shelf_path, '/compliance-schedule?view=certificates'),
      byScheme,
      soonest,
    },
    sorNote: typeof root.sor_note === 'string' ? root.sor_note : null,
  }
}
