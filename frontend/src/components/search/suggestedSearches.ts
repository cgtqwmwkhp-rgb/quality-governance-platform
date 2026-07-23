/** Structured suggestion chips for global search (honest, not AI theatre). */

export interface SuggestedSearch {
  id: string
  /** i18n key under search.suggestions.* */
  labelKey: string
  defaultLabel: string
  /** Navigate instead of running FTS when set */
  navigate?: string
  params: {
    q: string
    module?: string
    status?: string
    date_from?: string
    date_to?: string
  }
}

function formatLocalDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function monthBounds(today = new Date()): { date_from: string; date_to: string } {
  const start = new Date(today.getFullYear(), today.getMonth(), 1)
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  return { date_from: formatLocalDate(start), date_to: formatLocalDate(end) }
}

export function getSuggestedSearches(today = new Date()): SuggestedSearch[] {
  const month = monthBounds(today)
  return [
    {
      id: 'overdue-actions',
      labelKey: 'search.suggestions.overdue_actions',
      defaultLabel: 'Overdue actions',
      navigate: '/actions?view=my_overdue',
      params: {
        q: 'action',
        module: 'Actions',
        status: 'overdue,open',
      },
    },
    {
      id: 'high-priority-incidents',
      labelKey: 'search.suggestions.high_priority_incidents',
      defaultLabel: 'High-priority incidents',
      params: {
        q: 'critical high',
        module: 'Incidents',
        status: 'open,reported,under_investigation',
      },
    },
    {
      id: 'pending-audits-month',
      labelKey: 'search.suggestions.pending_audits_month',
      defaultLabel: 'Pending audits this month',
      params: {
        q: 'audit',
        module: 'Audits',
        status: 'open,pending,scheduled,in_progress',
        ...month,
      },
    },
    {
      id: 'unresolved-complaints',
      labelKey: 'search.suggestions.unresolved_complaints',
      defaultLabel: 'Unresolved complaints',
      params: {
        q: 'complaint',
        module: 'Complaints',
        status: 'open,received,under_investigation,in_progress',
      },
    },
  ]
}

export function dateRangeToBounds(
  dateRange: string,
  today = new Date(),
): { date_from?: string; date_to?: string } {
  if (dateRange === 'all') return {}
  const end = formatLocalDate(today)
  if (dateRange === 'today') {
    return { date_from: end, date_to: end }
  }
  if (dateRange === 'week') {
    const start = new Date(today)
    start.setDate(today.getDate() - 7)
    return { date_from: formatLocalDate(start), date_to: end }
  }
  if (dateRange === 'month') {
    return monthBounds(today)
  }
  return {}
}
