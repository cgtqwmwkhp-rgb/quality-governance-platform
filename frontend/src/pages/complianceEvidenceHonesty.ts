/**
 * Auditor-facing CEL honesty for /compliance.
 * A file or an AI proposal is not coverage. Confirmed conformance is.
 */

export type CoverageLink = {
  status?: string | null
  signal_type?: string | null
  linked_by?: string | null
  confirmed_at?: string | null
}

const OPERATIONAL_SIGNALS = new Set(['nonconformity', 'gap', 'opportunity'])

function norm(value: string | null | undefined): string {
  return (value || '').trim().toLowerCase()
}

export function isRejectedLink(link: CoverageLink): boolean {
  return norm(link.status) === 'rejected'
}

export function isProposedLink(link: CoverageLink): boolean {
  const status = norm(link.status)
  if (status === 'proposed' || status === 'needs_review') return true
  if (status === 'confirmed' || status === 'rejected') return false
  if (link.confirmed_at) return false
  return norm(link.linked_by) !== 'manual'
}

export function isAuditorConfirmedConformance(link: CoverageLink): boolean {
  if (isRejectedLink(link)) return false
  if (OPERATIONAL_SIGNALS.has(norm(link.signal_type))) return false

  const status = norm(link.status)
  if (status === 'proposed' || status === 'needs_review') return false
  if (status === 'confirmed' || Boolean(link.confirmed_at)) return true
  // Legacy payload with no status: only a manual link counts.
  return !status && norm(link.linked_by) === 'manual'
}

export function sourceIdentityLabel(link: { entity_type: string; entity_id: string }): string {
  return `${link.entity_type} ${link.entity_id}`
}
