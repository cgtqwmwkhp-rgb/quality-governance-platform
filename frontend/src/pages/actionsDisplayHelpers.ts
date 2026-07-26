/** User-facing labels for unified action source types (PX-152 / PX-233). */

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
