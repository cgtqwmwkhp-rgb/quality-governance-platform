/** Document detail tab helpers — Standards & Evidence deeplink + proposed scroll. */
export const DOCUMENT_DETAIL_TABS = [
  'overview',
  'evidence',
  'relationships',
  'versions',
  'quiz',
  'campaign-results',
  'qa',
  'watch',
] as const

export type DocumentDetailTab = (typeof DOCUMENT_DETAIL_TABS)[number]

export const PROPOSED_EVIDENCE_ANCHOR_ID = 'proposed-evidence-links'

export interface DocumentDetailTabOptions {
  /** Doc Graph flag state. The Relationships tab does not exist while it is closed. */
  documentGraphEnabled?: boolean
}

export function resolveDocumentDetailTab(
  raw: string | null | undefined,
  options?: DocumentDetailTabOptions,
): DocumentDetailTab {
  if (raw && (DOCUMENT_DETAIL_TABS as readonly string[]).includes(raw)) {
    if (raw === 'relationships' && !(options?.documentGraphEnabled ?? true)) {
      return 'overview'
    }
    return raw as DocumentDetailTab
  }
  return 'overview'
}

export function documentEvidenceHref(id: string | number): string {
  return `/documents/${id}?tab=evidence`
}

export function documentRelationshipsHref(id: string | number): string {
  return `/documents/${id}?tab=relationships`
}

/** True when URL asks for Standards & Evidence (optionally with proposed scroll). */
export function shouldScrollToProposedEvidence(
  tab: string | null | undefined,
  hash?: string | null,
): boolean {
  if (resolveDocumentDetailTab(tab) !== 'evidence') return false
  if (!hash) return true
  const normalized = hash.replace(/^#/, '')
  return normalized === '' || normalized === PROPOSED_EVIDENCE_ANCHOR_ID
}
