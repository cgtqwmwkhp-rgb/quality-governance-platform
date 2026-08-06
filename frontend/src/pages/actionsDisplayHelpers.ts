/**
 * User-facing labels for unified action source types (PX-152 / PX-233) and for
 * action ownership (PX-151).
 */

const SOURCE_TYPE_LABELS: Record<string, string> = {
  incident: 'Incident',
  capa_incident: 'Incident',
  investigation: 'Investigation',
  audit_finding: 'Audit finding',
  near_miss: 'Near miss',
  rta: 'RTA',
  complaint: 'Complaint',
  capa_complaint: 'Complaint',
  capa: 'CAPA',
  assessment: 'Assessment',
  induction: 'Induction',
  compliance_record: 'Compliance record',
}

/** True when a source reference looks like an internal storage key (`investigation:6`). */
export function isInternalSourceReference(value: string): boolean {
  const trimmed = value.trim()
  return /^[a-z_]+:\d+$/i.test(trimmed)
}

/** Prefer hydrated API source_reference; never surface raw enum/storage keys. */
export function formatActionSourceRef(input: {
  source_type: string
  source_id: number
  source_reference?: string | null
  source_title?: string | null
}): string {
  const ref = input.source_reference?.trim()
  if (ref && !isInternalSourceReference(ref)) {
    return ref
  }
  const title = input.source_title?.trim()
  if (title) return title
  const kind = (input.source_type || '').toLowerCase()
  const label = SOURCE_TYPE_LABELS[kind] || kind.replace(/_/g, ' ')
  if (!label) return `Source #${input.source_id}`
  return `${label} #${input.source_id}`
}

/**
 * Ownership as the action surfaces should state it.
 *
 * `assigned_unnamed` exists because the Actions list and the dashboard count key off
 * different things: the dashboard's "N assigned" counts `owner_id`, while the list can
 * only print a resolved name or email. When an action has an owner whose name did not
 * resolve, printing "Unassigned" contradicts the dashboard and tells the reader nobody
 * is accountable — so it is never printed for an owned action (PX-151).
 */
export type ActionAssigneeState = 'assigned' | 'assigned_unnamed' | 'unassigned'

export interface ActionAssigneeDisplay {
  label: string
  state: ActionAssigneeState
  /** The resolved name/email, when there is one. */
  name?: string
}

export const ASSIGNEE_UNRESOLVED_LABEL = 'Assigned — owner name unavailable'
export const ASSIGNEE_UNASSIGNED_LABEL = 'Unassigned'

export function resolveActionAssignee(input: {
  owner_id?: number | null
  owner_email?: string | null
  assigned_to_email?: string | null
}): ActionAssigneeDisplay {
  const name = (input.assigned_to_email || input.owner_email || '').trim()
  if (name) {
    return { label: name, state: 'assigned', name }
  }
  const ownerId = input.owner_id
  if (typeof ownerId === 'number' && Number.isFinite(ownerId) && ownerId > 0) {
    return { label: ASSIGNEE_UNRESOLVED_LABEL, state: 'assigned_unnamed' }
  }
  return { label: ASSIGNEE_UNASSIGNED_LABEL, state: 'unassigned' }
}
