/** Status helpers for Compliance Schedule — never use "Expired". */

import type { ComplianceStatus } from '../api/complianceScheduleClient'

export function statusLabel(status: ComplianceStatus | null | undefined): string {
  switch (status) {
    case 'current':
      return 'Current'
    case 'due_soon':
      return 'Due soon'
    case 'overdue':
      return 'Overdue'
    default:
      return '—'
  }
}

export function statusChipClass(status: ComplianceStatus | null | undefined): string {
  switch (status) {
    case 'current':
      return 'bg-emerald-500/10 text-emerald-700'
    case 'due_soon':
      return 'bg-amber-500/10 text-amber-800'
    case 'overdue':
      return 'bg-red-500/10 text-red-700'
    default:
      return 'bg-muted text-muted-foreground'
  }
}

export function deriveStatusFromDue(
  nextDue: string | null | undefined,
  now: Date = new Date(),
  dueSoonDays = 30,
): ComplianceStatus | null {
  if (!nextDue) return null
  const due = new Date(nextDue)
  if (Number.isNaN(due.getTime())) return null
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  const dueDay = new Date(Date.UTC(due.getUTCFullYear(), due.getUTCMonth(), due.getUTCDate()))
  const delta = Math.round((dueDay.getTime() - today.getTime()) / 86_400_000)
  if (delta < 0) return 'overdue'
  if (delta <= dueSoonDays) return 'due_soon'
  return 'current'
}
