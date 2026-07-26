import type { AuditFinding } from '../api/client'

/** Statuses that remain actionable on the Audits findings register (not closed). */
export const OPEN_AUDIT_FINDING_STATUSES = new Set([
  'open',
  'in_progress',
  'pending_verification',
  'deferred',
])

export function normalizeFindingStatus(status: string | null | undefined): string {
  return (status ?? 'open').trim().toLowerCase()
}

export function isOpenAuditFinding(status: string | null | undefined): boolean {
  return OPEN_AUDIT_FINDING_STATUSES.has(normalizeFindingStatus(status))
}

export function countOpenAuditFindings(findings: readonly AuditFinding[]): number {
  return findings.filter((finding) => isOpenAuditFinding(finding.status)).length
}

/**
 * Prefer the server-reported open total when available; fall back to the loaded slice.
 * When the loaded page is truncated, never pretend the slice is the full tenant total.
 */
export function resolveOpenFindingsKpi(
  loadedFindings: readonly AuditFinding[],
  serverOpenTotal: number | null,
  loadedTotal: number | null,
): number {
  const inScopeOpen = countOpenAuditFindings(loadedFindings)
  if (loadedTotal != null && loadedTotal > loadedFindings.length && serverOpenTotal != null) {
    return serverOpenTotal
  }
  return inScopeOpen
}
