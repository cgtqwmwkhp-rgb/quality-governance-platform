/**
 * Portal honesty helpers — display formatting and badge math shared across hub/work/track.
 */

const TERMINAL_ACTION_STATUSES = new Set(['completed', 'closed', 'cancelled', 'verified'])

/** Open assigned actions on the fetched page for hub badge (PX-305). */
export function countOpenAssignedActions(
  items: Array<{ status?: string; display_status?: string }>,
): number {
  return items.filter(
    (item) => !TERMINAL_ACTION_STATUSES.has((item.display_status || item.status || '').toLowerCase()),
  ).length
}

/** Known customer codes → display labels (PX-299 / PX-318). */
const CUSTOMER_DISPLAY: Record<string, string> = {
  plantexpand_ltd: 'Plantexpand Ltd',
  plantexpand: 'Plantexpand Ltd',
  ukpn: 'UK Power Networks',
  defra: 'DEFRA',
  openreach: 'Openreach',
  thames_water: 'Thames Water',
  cadent: 'Cadent',
  network_rail: 'Network Rail',
  novuna: 'Novuna',
}

/** Turn a lookup code / slug into an employee-facing customer name. */
export function humanizeCustomerCode(code: string): string {
  const trimmed = code.trim()
  if (!trimmed) return trimmed
  const known = CUSTOMER_DISPLAY[trimmed.toLowerCase()]
  if (known) return known
  if (!/[_-]/.test(trimmed) && trimmed === trimmed.toLowerCase()) {
    return trimmed.toUpperCase()
  }
  return trimmed
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

/** Rewrite generic type-plus-slug titles for track lists (PX-299 / PX-318). */
export function formatPortalReportTitle(title: string): string {
  if (!title) return title
  const match = /^(.*)\s-\s(.+)$/.exec(title.trim())
  if (!match) return title
  const [, prefix, suffix] = match
  const humanized = humanizeCustomerCode(suffix)
  if (humanized === suffix) return title
  return `${prefix} - ${humanized}`
}

/** Consistent portal date display — dd/mm/yyyy (PX-317). */
export function formatPortalDate(value: string | Date | null | undefined): string {
  if (!value) return ''
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleDateString('en-GB')
}
