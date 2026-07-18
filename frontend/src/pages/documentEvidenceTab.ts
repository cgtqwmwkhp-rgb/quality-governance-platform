/** Document detail tab helpers — Standards & Evidence deeplink + proposed scroll. */
export const DOCUMENT_DETAIL_TABS = [
  'overview',
  'evidence',
  'versions',
  'quiz',
  'campaign-results',
  'qa',
  'watch',
] as const

export type DocumentDetailTab = (typeof DOCUMENT_DETAIL_TABS)[number]

export const PROPOSED_EVIDENCE_ANCHOR_ID = 'proposed-evidence-links'

export function resolveDocumentDetailTab(
  raw: string | null | undefined,
): DocumentDetailTab {
  if (raw && (DOCUMENT_DETAIL_TABS as readonly string[]).includes(raw)) {
    return raw as DocumentDetailTab
  }
  return 'overview'
}

export function documentEvidenceHref(id: string | number): string {
  return `/documents/${id}?tab=evidence`
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
