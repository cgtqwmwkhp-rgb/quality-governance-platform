/** Honesty helpers for the portal assigned-audit queue. No fake zeros, no ??? rows. */

export type AssignedAuditRow = {
  reference_number?: string | null
  status?: string | null
}

export function isShowableAssignedAudit(run: AssignedAuditRow): boolean {
  const ref = (run.reference_number ?? '').trim()
  if (!ref || ref === '???') return false
  const status = (run.status ?? '').trim().toLowerCase()
  if (!status || status === 'unknown') return false
  if (status === 'completed' || status === 'cancelled') return false
  return true
}

export function isShowableCompletedAudit(run: AssignedAuditRow): boolean {
  const ref = (run.reference_number ?? '').trim()
  if (!ref || ref === '???') return false
  const status = (run.status ?? '').trim().toLowerCase()
  return status === 'completed'
}

export function assignedAuditQueueTotal(
  serverTotal: number | undefined,
  loadFailed: boolean,
): number | null {
  if (loadFailed) return null
  if (typeof serverTotal !== 'number' || Number.isNaN(serverTotal) || serverTotal < 0) {
    return null
  }
  return serverTotal
}
