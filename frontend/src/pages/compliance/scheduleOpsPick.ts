/**
 * SG-D-04 — pick the soonest matching Schedule obligation for a workspace cell.
 *
 * Schedule remains SoR. This is a read of the existing register, not a second
 * owner table and not a cell-aggregate fork (D2 lock).
 */
import { obligationMentionsClause } from './scheduleProgrammeContext'

export type ScheduleNotifyBand = 'none' | 'due_60' | 'due_30' | 'due_7' | 'overdue'

export type ScheduleOpsItem = {
  reference_number: string
  title: string
  description?: string | null
  regulatory_basis?: string | null
  owner_name?: string | null
  next_due_date: string
  status?: 'current' | 'due_soon' | 'overdue' | null
}

export type ScheduleOpsPick = {
  reference_number: string
  title: string
  owner_name: string | null
  next_due_date: string
  days_remaining: number
  status: 'current' | 'due_soon' | 'overdue' | null
  notify_band: ScheduleNotifyBand
}

/** Same exclusive windows as `classify_due_band` in compliance_schedule_policy. */
export function notifyBandForDays(daysRemaining: number): ScheduleNotifyBand {
  if (daysRemaining < 0) return 'overdue'
  if (daysRemaining <= 7) return 'due_7'
  if (daysRemaining <= 30) return 'due_30'
  if (daysRemaining <= 60) return 'due_60'
  return 'none'
}

function utcToday(isoDate: string): string {
  return isoDate.slice(0, 10)
}

function daysBetween(todayIso: string, dueIso: string): number {
  const today = Date.parse(`${utcToday(todayIso)}T00:00:00Z`)
  const due = Date.parse(`${utcToday(dueIso)}T00:00:00Z`)
  return Math.round((due - today) / 86_400_000)
}

export function pickSoonestMatchingObligation(
  items: ScheduleOpsItem[],
  clause: string,
  todayIsoDate: string,
): ScheduleOpsPick | null {
  const matches = items.filter((item) => obligationMentionsClause(item, clause))
  if (matches.length === 0) return null

  const sorted = [...matches].sort((a, b) =>
    utcToday(a.next_due_date).localeCompare(utcToday(b.next_due_date)),
  )
  const soonest = sorted[0]
  if (!soonest) return null

  const days_remaining = daysBetween(todayIsoDate, soonest.next_due_date)
  return {
    reference_number: soonest.reference_number,
    title: soonest.title,
    owner_name: soonest.owner_name?.trim() ? soonest.owner_name : null,
    next_due_date: utcToday(soonest.next_due_date),
    days_remaining,
    status: soonest.status ?? null,
    notify_band: notifyBandForDays(days_remaining),
  }
}
