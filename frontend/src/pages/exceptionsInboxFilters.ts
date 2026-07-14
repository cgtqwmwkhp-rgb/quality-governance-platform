/**
 * Knowledge Exceptions inbox filter helpers — status + entity_type + signal_type with URL sync.
 */

export {
  exceptionEntityHref,
  isSafeReturnTo,
  knowledgeExceptionsClosedLoopHref,
  parseEntityTypeFilter,
} from '../helpers/knowledgeExceptionsLinks'

export const EXCEPTIONS_STATUS_OPTIONS = [
  { value: 'inbox', label: 'Inbox (proposed + needs review)' },
  { value: 'proposed', label: 'Proposed' },
  { value: 'needs_review', label: 'Needs review' },
] as const

export const EXCEPTIONS_ENTITY_TYPE_OPTIONS = [
  { value: 'all', label: 'All entity types' },
  { value: 'document', label: 'Document' },
  { value: 'incident', label: 'Incident' },
  { value: 'complaint', label: 'Complaint' },
  { value: 'near_miss', label: 'Near miss' },
  { value: 'rta', label: 'RTA' },
  { value: 'audit_finding', label: 'Audit finding' },
] as const

export const EXCEPTIONS_SIGNAL_TYPE_OPTIONS = [
  { value: 'all', label: 'All signal types' },
  { value: 'evidence', label: 'Evidence' },
  { value: 'nonconformity', label: 'Nonconformity' },
  { value: 'gap', label: 'Gap' },
  { value: 'opportunity', label: 'Opportunity' },
] as const

export type ExceptionsStatusFilter = (typeof EXCEPTIONS_STATUS_OPTIONS)[number]['value']
export type ExceptionsEntityTypeFilter =
  (typeof EXCEPTIONS_ENTITY_TYPE_OPTIONS)[number]['value']
export type ExceptionsSignalTypeFilter =
  (typeof EXCEPTIONS_SIGNAL_TYPE_OPTIONS)[number]['value']

export function parseExceptionsStatusFilter(
  raw: string | null | undefined,
): ExceptionsStatusFilter {
  if (raw === 'proposed' || raw === 'needs_review' || raw === 'inbox') return raw
  return 'inbox'
}

export function parseExceptionsEntityTypeFilter(
  raw: string | null | undefined,
): ExceptionsEntityTypeFilter {
  if (!raw || raw === 'all') return 'all'
  if (
    (EXCEPTIONS_ENTITY_TYPE_OPTIONS as readonly { value: string }[]).some(
      (o) => o.value === raw,
    )
  ) {
    return raw as ExceptionsEntityTypeFilter
  }
  return 'all'
}

export function parseExceptionsSignalTypeFilter(
  raw: string | null | undefined,
): ExceptionsSignalTypeFilter {
  if (!raw || raw === 'all') return 'all'
  if (
    (EXCEPTIONS_SIGNAL_TYPE_OPTIONS as readonly { value: string }[]).some(
      (o) => o.value === raw,
    )
  ) {
    return raw as ExceptionsSignalTypeFilter
  }
  return 'all'
}

/** Map UI status filter to API `status` query (omit for default inbox). */
export function exceptionsStatusQueryParam(
  filter: ExceptionsStatusFilter,
): string | undefined {
  if (filter === 'inbox') return undefined
  return filter
}

/**
 * Build shareable inbox query string. Omits defaults (inbox / all / all).
 */
export function buildExceptionsInboxSearch(params: {
  status: ExceptionsStatusFilter
  entityType: ExceptionsEntityTypeFilter
  signalType: ExceptionsSignalTypeFilter
}): string {
  const sp = new URLSearchParams()
  if (params.status !== 'inbox') sp.set('status', params.status)
  if (params.entityType !== 'all') sp.set('entity_type', params.entityType)
  if (params.signalType !== 'all') sp.set('signal_type', params.signalType)
  return sp.toString()
}
