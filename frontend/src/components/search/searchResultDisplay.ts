/**
 * Display helpers for Global Search results — especially document_content hits.
 * Backend may return ts_headline markup in description, word highlights, and
 * the sentinel `snippet_suppressed` when body text must not be shown.
 */

export const SNIPPET_SUPPRESSED = 'snippet_suppressed'

export const DOCUMENT_CONTENT_MODULE = 'Document Content'

export const COMPLIANCE_SCHEDULE_MODULE = 'Compliance Schedule'

/** Filter / facet chip value → clearer chip label (value stays API-aligned). */
export const MODULE_FILTER_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'Incidents', label: 'Incidents' },
  { value: 'RTAs', label: 'RTAs' },
  { value: 'Complaints', label: 'Complaints' },
  { value: 'Risks', label: 'Risks' },
  { value: 'Audits', label: 'Audits' },
  { value: 'Actions', label: 'Actions' },
  { value: 'Documents', label: 'Documents' },
  { value: DOCUMENT_CONTENT_MODULE, label: 'Document body' },
  { value: COMPLIANCE_SCHEDULE_MODULE, label: 'Compliance' },
]

export function isSnippetSuppressed(highlights: string[] | null | undefined): boolean {
  return (highlights ?? []).includes(SNIPPET_SUPPRESSED)
}

export function isDocumentContentResult(result: {
  type?: string | null
  module?: string | null
}): boolean {
  return result.type === 'document_content' || result.module === DOCUMENT_CONTENT_MODULE
}

export function moduleDisplayLabel(module: string): string {
  const match = MODULE_FILTER_OPTIONS.find((option) => option.value === module)
  return match?.label ?? module
}

export function parsePageFromSearchPath(path: string | null | undefined): number | null {
  if (!path || !path.includes('?')) return null
  const query = path.slice(path.indexOf('?') + 1)
  const page = new URLSearchParams(query).get('page')
  if (!page) return null
  const n = Number(page)
  return Number.isFinite(n) && n > 0 ? n : null
}

export interface SearchLocationMeta {
  heading: string | null
  page: number | null
}

/** Prefer explicit API fields; fall back to `page` on the deep-link path. */
export function getSearchLocationMeta(result: {
  heading?: string | null
  page_number?: number | null
  path?: string | null
}): SearchLocationMeta {
  const heading = typeof result.heading === 'string' ? result.heading.trim() || null : null
  const explicitPage =
    typeof result.page_number === 'number' && result.page_number > 0 ? result.page_number : null
  return {
    heading,
    page: explicitPage ?? parsePageFromSearchPath(result.path),
  }
}

/** Strip Postgres ts_headline `<b>` wrappers (and any other tags) for safe text. */
export function stripHeadlineMarkup(text: string): string {
  // Loop until stable so nested/partial tags cannot reconstitute markup (CodeQL).
  let result = text
  let previous = ''
  while (result !== previous) {
    previous = result
    result = result.replace(/<[^>]*>/g, '')
  }
  return result
}

function termsFromHeadlineMarkup(description: string): string[] {
  const terms: string[] = []
  for (const match of description.matchAll(/<b>(.*?)<\/b>/gi)) {
    const term = match[1]?.trim()
    if (term) terms.push(term)
  }
  return terms
}

export function collectHighlightTerms(
  highlights: string[] | null | undefined,
  description?: string | null,
): string[] {
  const fromApi = (highlights ?? []).filter((h) => h && h !== SNIPPET_SUPPRESSED)
  const fromMarkup = description ? termsFromHeadlineMarkup(description) : []
  const seen = new Set<string>()
  const out: string[] = []
  for (const term of [...fromApi, ...fromMarkup]) {
    const key = term.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(term)
  }
  return out
}

export type SnippetSegment = { text: string; highlighted: boolean }

export function buildHighlightedSegments(
  description: string,
  highlights: string[] | null | undefined,
): SnippetSegment[] {
  const plain = stripHeadlineMarkup(description)
  if (!plain) return []

  const terms = collectHighlightTerms(highlights, description)
  if (!terms.length) return [{ text: plain, highlighted: false }]

  const escaped = terms
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .filter(Boolean)
  if (!escaped.length) return [{ text: plain, highlighted: false }]

  const re = new RegExp(`(${escaped.join('|')})`, 'gi')
  const parts = plain.split(re)
  const termKeys = new Set(terms.map((t) => t.toLowerCase()))

  return parts
    .filter((part) => part.length > 0)
    .map((part) => ({
      text: part,
      highlighted: termKeys.has(part.toLowerCase()),
    }))
}
