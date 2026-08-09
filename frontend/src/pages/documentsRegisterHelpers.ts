/**
 * Master Document Register list projection helpers (WA-1 / L-01 / L-05 / L-05b)
 * + WA-3 / L-08 status tone (greyscale + SR-legible icon key).
 *
 * Open paths prefer the API `href` field projected via server
 * `href_registry.document_href` — callers must not invent parallel SPA builders
 * when the list payload already carries `href`.
 */

export interface DocumentRegisterRefInput {
  id: number
  reference_number: string
  pel_doc_ref?: string | null
  href?: string | null
}

export interface DocumentRegisterPrimaryRef {
  /** Auditor-facing lead: PEL when present, else DOC / reference_number. */
  lead: string
  /** Secondary chip when PEL leads (typically DOC-YYYY-####). */
  secondary: string | null
  hasPel: boolean
}

export type DocumentRegisterStatusIcon = 'check' | 'clock' | 'loader' | 'alert' | 'dot'

export interface DocumentRegisterStatusTone {
  /** Greyscale badge variant — colour is never the sole status cue (L-08). */
  variant: 'closed' | 'secondary' | 'outline'
  icon: DocumentRegisterStatusIcon
  /** Raw status string for visible + SR text. */
  label: string
}

/**
 * Resolve the Register Hyperlink target for a filed library document.
 *
 * Prefer list-projection `href` from `href_registry`. Fallback mirrors
 * `document_href(id)` so filed rows are never blank when a fixture omits `href`.
 */
export function resolveDocumentRegisterHref(doc: {
  id: number
  href?: string | null
}): string {
  const href = typeof doc.href === 'string' ? doc.href.trim() : ''
  if (href.startsWith('/')) {
    return href
  }
  return `/documents/${doc.id}`
}

/** PEL is the Register lead identifier when allocated; DOC remains secondary. */
export function documentRegisterPrimaryRef(doc: {
  reference_number?: string | null
  pel_doc_ref?: string | null
}): DocumentRegisterPrimaryRef {
  const pel = typeof doc.pel_doc_ref === 'string' ? doc.pel_doc_ref.trim() : ''
  const reference =
    (typeof doc.reference_number === 'string' ? doc.reference_number : '').trim() ||
    'DOC-UNKNOWN'
  if (pel) {
    return { lead: pel, secondary: reference, hasPel: true }
  }
  return { lead: reference, secondary: null, hasPel: false }
}

/**
 * Greyscale status tone for Register cells (L-08).
 * Hue is never the only cue — callers pair this with an icon keyed by `icon`.
 */
export function documentRegisterStatusTone(
  status?: string | null,
): DocumentRegisterStatusTone {
  const label = (typeof status === 'string' ? status : '').trim() || 'unknown'
  switch (label) {
    case 'indexed':
    case 'approved':
      return { variant: 'closed', icon: 'check', label }
    case 'processing':
      return { variant: 'closed', icon: 'loader', label }
    case 'pending':
      return { variant: 'closed', icon: 'clock', label }
    case 'failed':
      return { variant: 'closed', icon: 'alert', label }
    default:
      return { variant: 'closed', icon: 'dot', label }
  }
}
