import type { KnowledgeEvidenceLink } from '../api/knowledgeBankClient'

export interface ParsedEvidenceQuote {
  snippet: string | null
  page: number | null
  rationaleWithoutQuote: string | null
}

const GENERIC_RATIONALE_PREFIXES = [
  'UVDB keyword match',
  'Planet Mark theme match',
  'KB reverse-scan match',
  'ISO auto-tag match',
]

const PAGE_IN_TEXT =
  /(?:\(p\.?\s*(\d+)\)|\(page\s*(\d+)\)|\[page\s*(\d+)\]|(?:^|\s|on\s+)page\s*(\d+)(?:\s|[-–:]|$)|(?:^|\s)p\.\s*(\d+))/i

function firstCapturedPage(match: RegExpMatchArray): number | null {
  for (let i = 1; i < match.length; i += 1) {
    const value = match[i]
    if (value) {
      const page = Number(value)
      if (!Number.isNaN(page)) return page
    }
  }
  return null
}

export function parseEvidenceQuote(link: KnowledgeEvidenceLink): ParsedEvidenceQuote {
  if (link.evidence_snippet?.trim()) {
    return {
      snippet: link.evidence_snippet.trim(),
      page: link.source_page ?? null,
      rationaleWithoutQuote: link.rationale,
    }
  }

  const rationale = link.rationale?.trim() ?? null
  if (!rationale) {
    return { snippet: null, page: null, rationaleWithoutQuote: null }
  }

  let page = link.source_page ?? null
  if (page == null && link.notes) {
    const noteMatch = link.notes.match(/page\s*(\d+)/i)
    if (noteMatch) page = Number(noteMatch[1])
  }

  const pageMatch = rationale.match(PAGE_IN_TEXT)
  if (pageMatch && page == null) {
    page = firstCapturedPage(pageMatch)
  }

  const isGeneric = GENERIC_RATIONALE_PREFIXES.some((prefix) => rationale.startsWith(prefix))
  if (!isGeneric && rationale.length > 10) {
    return { snippet: rationale, page, rationaleWithoutQuote: null }
  }

  const quoteMatch = rationale.match(/[“"]([^”"]+)[”"]|'([^']+)'/)
  if (quoteMatch) {
    const snippet = (quoteMatch[1] ?? quoteMatch[2]).trim()
    const rationaleWithoutQuote = rationale.replace(quoteMatch[0], '').trim() || null
    return { snippet, page, rationaleWithoutQuote }
  }

  return { snippet: null, page, rationaleWithoutQuote: rationale }
}

export function isProposedEvidenceLink(link: KnowledgeEvidenceLink): boolean {
  return link.status === 'proposed' || link.status === 'needs_review'
}
