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

export const EXCEPTIONS_GATE_REASON_OPTIONS = [
  { value: 'all', label: 'All ingest gate reasons' },
  { value: 'below_threshold', label: 'Below 98% confidence' },
  { value: 'matrix_not_loaded', label: 'Matrix not loaded' },
  { value: 'strict_doc_type', label: 'Strict document type' },
  { value: 'alignment_near_requires_addition', label: 'NEAR — addition not attested' },
  { value: 'alignment_not_exact_for_framework', label: 'Not EXACT for this framework' },
  { value: 'alignment_not_exact', label: 'Not EXACT' },
  { value: 'alignment_different', label: 'DIFFERENT row' },
  { value: 'alignment_unique', label: 'UNIQUE row' },
  { value: 'cover_blocked_open_nc', label: 'Cover blocked — open NC' },
  { value: 'cover_blocked_open_action', label: 'Cover blocked — open action' },
  { value: 'unparseable_clause', label: 'Unparseable clause' },
  { value: 'operational_entity', label: 'Operational entity (always proposed)' },
] as const

export type ExceptionsStatusFilter = (typeof EXCEPTIONS_STATUS_OPTIONS)[number]['value']
export type ExceptionsEntityTypeFilter =
  (typeof EXCEPTIONS_ENTITY_TYPE_OPTIONS)[number]['value']
export type ExceptionsSignalTypeFilter =
  (typeof EXCEPTIONS_SIGNAL_TYPE_OPTIONS)[number]['value']
export type ExceptionsGateReasonFilter =
  (typeof EXCEPTIONS_GATE_REASON_OPTIONS)[number]['value']

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

export function parseExceptionsGateReasonFilter(
  raw: string | null | undefined,
): ExceptionsGateReasonFilter {
  if (!raw || raw === 'all') return 'all'
  if (
    (EXCEPTIONS_GATE_REASON_OPTIONS as readonly { value: string }[]).some(
      (o) => o.value === raw,
    )
  ) {
    return raw as ExceptionsGateReasonFilter
  }
  return 'all'
}

export function formatGateReasonLabel(reason: string | null | undefined): string {
  if (!reason) return 'Gate reason not logged'
  const match = EXCEPTIONS_GATE_REASON_OPTIONS.find((o) => o.value === reason)
  if (match && match.value !== 'all') return match.label
  return reason.replace(/_/g, ' ')
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
  gateReason: ExceptionsGateReasonFilter
}): string {
  const sp = new URLSearchParams()
  if (params.status !== 'inbox') sp.set('status', params.status)
  if (params.entityType !== 'all') sp.set('entity_type', params.entityType)
  if (params.signalType !== 'all') sp.set('signal_type', params.signalType)
  if (params.gateReason !== 'all') sp.set('gate_reason', params.gateReason)
  return sp.toString()
}
