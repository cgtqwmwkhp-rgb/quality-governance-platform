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

export function normalizeClauseNeedle(clause: string): string {
  return clause.trim().toLowerCase().replace(/\s+/g, '')
}

type ClauseMatchable = {
  clause_ids?: ReadonlyArray<unknown> | null
  title?: string
  description?: string
}

/**
 * Honour `/audits?clause=` from Compliance. Match stringified clause_ids
 * (imports store "7.2") and a bounded mention in title/description.
 * Do not treat integer catalog ids as clause numbers.
 */
export function findingMatchesClause(finding: ClauseMatchable, clause: string): boolean {
  const needle = normalizeClauseNeedle(clause)
  if (!needle) return true

  for (const id of finding.clause_ids ?? []) {
    if (typeof id === 'number' && Number.isFinite(id)) continue
    if (normalizeClauseNeedle(String(id)) === needle) return true
  }

  const haystack = `${finding.title ?? ''} ${finding.description ?? ''}`
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`(^|[^0-9a-z.])${escaped}([^0-9a-z]|$)`, 'i').test(haystack)
}

export function scopeFindingsToRunIds(
  findings: readonly AuditFinding[],
  runIds: ReadonlySet<number>,
): AuditFinding[] {
  return findings.filter((finding) => runIds.has(finding.run_id))
}

export type OpenFindingsKpiOptions = {
  /**
   * PX-262: when the loaded page is truncated, use the server open total.
   * A3: when the view is a programme / customer / clause subset, never use
   * the tenant-wide server total — count the scoped loaded slice only.
   */
  useServerTotalWhenTruncated?: boolean
}

/**
 * Prefer the server-reported open total when available; fall back to the loaded slice.
 * When the loaded page is truncated, never pretend the slice is the full tenant total.
 */
export function resolveOpenFindingsKpi(
  loadedFindings: readonly AuditFinding[],
  serverOpenTotal: number | null,
  loadedTotal: number | null,
  options?: OpenFindingsKpiOptions,
): number {
  const inScopeOpen = countOpenAuditFindings(loadedFindings)
  const useServer = options?.useServerTotalWhenTruncated !== false
  if (
    useServer &&
    loadedTotal != null &&
    loadedTotal > loadedFindings.length &&
    serverOpenTotal != null
  ) {
    return serverOpenTotal
  }
  return inScopeOpen
}
