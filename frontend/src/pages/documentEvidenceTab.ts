/**
 * Document Detail layer helpers (WB-1 / L-29).
 *
 * Canonical spine layers replace the previous eight tabs. Legacy `?tab=` values
 * remain permanent aliases so bookmarks and cross-module emitters keep working
 * without a twin Documents-360 page.
 */

export const DOCUMENT_DETAIL_LAYERS = [
  'control',
  'coverage',
  'related',
  'used-by',
  'history',
  'assurance',
  'preview',
] as const

export type DocumentDetailLayer = (typeof DOCUMENT_DETAIL_LAYERS)[number]

/** @deprecated Prefer DocumentDetailLayer — kept as alias for gradual call-site migration. */
export type DocumentDetailTab = DocumentDetailLayer

export const DOCUMENT_DETAIL_SECTIONS = [
  'quiz',
  'share',
  'qa',
  'watch',
  'campaign-results',
  'connections',
] as const

export type DocumentDetailSection = (typeof DOCUMENT_DETAIL_SECTIONS)[number]

export const PROPOSED_EVIDENCE_ANCHOR_ID = 'proposed-evidence-links'

/** Legacy tab query values → layer (+ optional in-layer section). */
export const LEGACY_TAB_ALIASES: Record<
  string,
  { layer: DocumentDetailLayer; section?: DocumentDetailSection }
> = {
  overview: { layer: 'control' },
  evidence: { layer: 'coverage' },
  relationships: { layer: 'related' },
  versions: { layer: 'history' },
  quiz: { layer: 'assurance', section: 'quiz' },
  qa: { layer: 'assurance', section: 'qa' },
  watch: { layer: 'assurance', section: 'watch' },
  'campaign-results': { layer: 'used-by', section: 'campaign-results' },
}

export interface DocumentDetailTabOptions {
  /**
   * Retained for call-site compatibility. Related is always a spine layer —
   * Doc Graph off shows an honest empty state rather than hiding the tab.
   */
  documentGraphEnabled?: boolean
}

function isLayer(value: string): value is DocumentDetailLayer {
  return (DOCUMENT_DETAIL_LAYERS as readonly string[]).includes(value)
}

/**
 * Resolve `?tab=` to a canonical layer.
 * Accepts both new layer ids and permanent legacy aliases.
 */
export function resolveDocumentDetailTab(
  raw: string | null | undefined,
  _options?: DocumentDetailTabOptions,
): DocumentDetailLayer {
  if (!raw) return 'control'
  if (isLayer(raw)) return raw
  const alias = LEGACY_TAB_ALIASES[raw]
  if (alias) return alias.layer
  return 'control'
}

/** Optional in-layer section for legacy deep links (quiz / qa / watch / campaign-results). */
export function resolveDocumentDetailSection(
  raw: string | null | undefined,
): DocumentDetailSection | null {
  if (!raw) return null
  if (isLayer(raw)) return null
  const alias = LEGACY_TAB_ALIASES[raw]
  return alias?.section ?? null
}

export function documentDetailSectionDomId(section: DocumentDetailSection): string {
  return `document-detail-section-${section}`
}

/**
 * Legacy emitter — still emits `?tab=evidence` so Knowledge Exceptions /
 * Compliance Evidence / Portal links stay byte-stable in WB-1.
 */
export function documentEvidenceHref(id: string | number): string {
  return `/documents/${id}?tab=evidence`
}

/**
 * Legacy emitter — still emits `?tab=relationships`.
 */
export function documentRelationshipsHref(id: string | number): string {
  return `/documents/${id}?tab=relationships`
}

/** New call sites: link to a canonical layer (optional section). */
export function documentLayerHref(
  id: string | number,
  layer: DocumentDetailLayer,
  section?: DocumentDetailSection,
): string {
  const base = `/documents/${id}?tab=${layer}`
  if (!section) return base
  return `${base}#${documentDetailSectionDomId(section)}`
}

/** True when URL asks for Coverage (optionally with proposed scroll). */
export function shouldScrollToProposedEvidence(
  tab: string | null | undefined,
  hash?: string | null,
): boolean {
  if (resolveDocumentDetailTab(tab) !== 'coverage') return false
  if (!hash) return true
  const normalized = hash.replace(/^#/, '')
  return normalized === '' || normalized === PROPOSED_EVIDENCE_ANCHOR_ID
}
