/**
 * Knowledge Exceptions inbox — standard/clause identity, why detail, stable de-dupe.
 * Pure helpers (KE-W1); safe to unit test without rendering.
 */
import { ISO_STANDARDS, type ISOClause } from '../data/isoStandards'

/** Minimal link shape for honesty helpers (matches KnowledgeEvidenceLink). */
export interface ExceptionLinkLike {
  id: number
  entity_type: string
  entity_id: string
  clause_id: string
  scheme: string | null
  status: string
  rationale: string | null
  title: string | null
  notes: string | null
  signal_type?: string | null
  confidence: number | null
  linked_by?: string | null
}

export interface ClauseIdentity {
  schemeKey: string | null
  schemeLabel: string
  clauseNumber: string
  clauseTitle: string | null
  sectionPath: string | null
  rawClauseId: string
}

export type ExceptionAllocationKind =
  | 'actionable'
  | 'already_confirmed'
  | 'already_rejected'
  | 'duplicate_proposal'

export interface DedupedExceptionRow {
  primary: ExceptionLinkLike
  duplicates: ExceptionLinkLike[]
  allocationKind: ExceptionAllocationKind
  allocationKey: string
}

const SCHEME_KEY_ALIASES: Record<string, string> = {
  iso9001: 'iso9001',
  'iso9001:2015': 'iso9001',
  iso14001: 'iso14001',
  iso45001: 'iso45001',
  iso27001: 'iso27001',
  uvdb: 'uvdb',
  'uvdb achilles': 'uvdb',
  achilles: 'uvdb',
  uvdb_achilles: 'uvdb',
  planetmark: 'planetmark',
  'planet mark': 'planetmark',
  planet_mark: 'planetmark',
}

const SCHEME_LABELS: Record<string, string> = {
  iso9001: 'ISO 9001',
  iso14001: 'ISO 14001',
  iso45001: 'ISO 45001',
  iso27001: 'ISO 27001',
  uvdb: 'UVDB Achilles',
  planetmark: 'Planet Mark',
}

const GENERIC_RATIONALE = [
  /^possible gap$/i,
  /^gap$/i,
  /^ai mapping$/i,
  /^mapped by ai$/i,
  /^potential (gap|nonconformity|opportunity)/i,
  /^needs review$/i,
  /^review recommended$/i,
  /^automated (mapping|link)$/i,
]

const STATUS_RANK: Record<string, number> = {
  confirmed: 0,
  rejected: 1,
  needs_review: 2,
  proposed: 3,
}

/** Normalize scheme slug for stable allocation keys. */
export function normalizeSchemeKey(scheme: string | null | undefined): string | null {
  if (!scheme) return null
  const trimmed = scheme.trim().toLowerCase()
  if (!trimmed) return null
  if (SCHEME_KEY_ALIASES[trimmed]) return SCHEME_KEY_ALIASES[trimmed]
  const isoMatch = trimmed.match(/^iso\s*(\d{4,5})/)
  if (isoMatch) return `iso${isoMatch[1]}`
  return trimmed.replace(/\s+/g, '_')
}

/** Human-readable standard family label. */
export function formatSchemeLabel(scheme: string | null | undefined): string {
  const key = normalizeSchemeKey(scheme)
  if (key && SCHEME_LABELS[key]) return SCHEME_LABELS[key]
  if (!scheme?.trim()) return 'Unknown standard'
  const upper = scheme.trim()
  if (/^iso\d/i.test(upper)) {
    return upper.replace(/^iso(\d+)/i, 'ISO $1')
  }
  return upper
}

/** Infer scheme key from clause_id when scheme column is missing. */
export function inferSchemeKeyFromClauseId(clauseId: string): string | null {
  const raw = clauseId.trim()
  if (!raw) return null
  const colonPrefix = raw.match(/^([a-z][a-z0-9_]*):/i)
  if (colonPrefix) {
    const prefix = colonPrefix[1].toLowerCase()
    if (prefix.startsWith('iso') && /\d/.test(prefix)) {
      const digits = prefix.match(/\d{4,5}/)
      return digits ? `iso${digits[0]}` : normalizeSchemeKey(prefix)
    }
    return normalizeSchemeKey(prefix)
  }
  const hyphenIso = raw.match(/^(\d{4,5})-/i)
  if (hyphenIso) return `iso${hyphenIso[1]}`
  const isoCompact = raw.match(/^iso\s*-?\s*(\d{4,5})/i)
  if (isoCompact) return `iso${isoCompact[1]}`
  return null
}

/** Extract clause number token from heterogeneous clause_id formats. */
export function extractClauseNumber(
  clauseId: string,
  schemeKey: string | null,
): string {
  const raw = clauseId.trim()
  if (!raw) return raw

  const afterColon = raw.includes(':') ? raw.split(':').slice(1).join(':').trim() : null
  if (afterColon) return afterColon

  const hyphenMatch = raw.match(/^(?:\d{4,5}|iso-?\d{4,5})-(.+)$/i)
  if (hyphenMatch) return hyphenMatch[1]

  if (schemeKey?.startsWith('iso') && /^\d/.test(raw)) return raw

  return raw
}

function clauseCatalogueForScheme(schemeKey: string | null): ISOClause[] {
  if (!schemeKey) return []
  return ISO_STANDARDS.find((s) => s.id === schemeKey)?.clauses ?? []
}

function findCatalogueClause(
  schemeKey: string | null,
  clauseNumber: string,
): ISOClause | null {
  if (!schemeKey || !clauseNumber) return null
  const normalized = clauseNumber.trim()
  const clauses = clauseCatalogueForScheme(schemeKey)
  const exact = clauses.find((c) => c.clauseNumber === normalized)
  if (exact) return exact
  return (
    clauses.find(
      (c) =>
        c.clauseNumber.replace(/\s+/g, '') === normalized.replace(/\s+/g, ''),
    ) ?? null
  )
}

function buildSectionPath(clause: ISOClause | null, schemeKey: string | null): string | null {
  if (!clause || !schemeKey) return null
  const clauses = clauseCatalogueForScheme(schemeKey)
  const byId = new Map(clauses.map((c) => [c.id, c]))
  const segments: string[] = []
  let current: ISOClause | undefined = clause
  while (current) {
    segments.unshift(`${current.clauseNumber} ${current.title}`)
    current = current.parentClause ? byId.get(current.parentClause) : undefined
  }
  return segments.length > 1 ? segments.slice(0, -1).join(' → ') : null
}

/** Resolve display identity for a standard + clause pair (KE-01, KE-02). */
export function resolveClauseIdentity(
  link: Pick<ExceptionLinkLike, 'scheme' | 'clause_id' | 'title'>,
): ClauseIdentity {
  const rawClauseId = link.clause_id?.trim() || '—'
  const schemeKey =
    normalizeSchemeKey(link.scheme) ?? inferSchemeKeyFromClauseId(rawClauseId)
  const clauseNumber = extractClauseNumber(rawClauseId, schemeKey)
  const catalogue = findCatalogueClause(schemeKey, clauseNumber)
  const schemeLabel = formatSchemeLabel(schemeKey ?? link.scheme)

  return {
    schemeKey,
    schemeLabel,
    clauseNumber,
    clauseTitle: catalogue?.title ?? link.title?.trim() ?? null,
    sectionPath: buildSectionPath(catalogue, schemeKey),
    rawClauseId,
  }
}

/** Stable allocation key: entity × scheme × clause (KE-04). */
export function exceptionAllocationKey(
  link: Pick<ExceptionLinkLike, 'entity_type' | 'entity_id' | 'scheme' | 'clause_id'>,
): string {
  const schemeKey =
    normalizeSchemeKey(link.scheme) ??
    inferSchemeKeyFromClauseId(link.clause_id) ??
    'unknown'
  const clauseNumber = extractClauseNumber(link.clause_id, schemeKey)
  return `${link.entity_type}:${link.entity_id}|${schemeKey}|${clauseNumber.toLowerCase()}`
}

function statusRank(status: string): number {
  return STATUS_RANK[status] ?? 99
}

function pickPrimaryLink(links: ExceptionLinkLike[]): ExceptionLinkLike {
  return [...links].sort((a, b) => {
    const rankDiff = statusRank(a.status) - statusRank(b.status)
    if (rankDiff !== 0) return rankDiff
    const confA = a.confidence ?? -1
    const confB = b.confidence ?? -1
    if (confB !== confA) return confB - confA
    return b.id - a.id
  })[0]
}

function allocationKindForGroup(
  primary: ExceptionLinkLike,
  duplicates: ExceptionLinkLike[],
): ExceptionAllocationKind {
  if (primary.status === 'confirmed') return 'already_confirmed'
  if (primary.status === 'rejected') return 'already_rejected'
  const hasConfirmed = duplicates.some((d) => d.status === 'confirmed')
  if (hasConfirmed) return 'already_confirmed'
  const hasRejected = duplicates.some((d) => d.status === 'rejected')
  if (hasRejected && (primary.status === 'proposed' || primary.status === 'needs_review')) {
    return 'already_rejected'
  }
  if (duplicates.length > 0) return 'duplicate_proposal'
  return 'actionable'
}

/**
 * Collapse twin proposals / show existing allocation honestly (KE-05).
 * Preserves server order within groups; newest/highest-confidence proposal wins ties.
 */
export function dedupeKnowledgeExceptions(items: ExceptionLinkLike[]): DedupedExceptionRow[] {
  const groups = new Map<string, ExceptionLinkLike[]>()
  for (const item of items) {
    const key = exceptionAllocationKey(item)
    const bucket = groups.get(key) ?? []
    bucket.push(item)
    groups.set(key, bucket)
  }

  const rows: DedupedExceptionRow[] = []
  for (const [allocationKey, group] of groups) {
    const primary = pickPrimaryLink(group)
    const duplicates = group.filter((item) => item.id !== primary.id)
    rows.push({
      primary,
      duplicates,
      allocationKey,
      allocationKind: allocationKindForGroup(primary, duplicates),
    })
  }

  return rows.sort((a, b) => b.primary.id - a.primary.id)
}

export function isGenericRationale(text: string | null | undefined): boolean {
  if (!text?.trim()) return true
  const value = text.trim()
  if (value.length < 12) return true
  return GENERIC_RATIONALE.some((pattern) => pattern.test(value))
}

export interface WhyDetail {
  summary: string
  lines: string[]
  isGeneric: boolean
}

/** Build specific why copy for hover/detail (KE-03). */
export function buildWhyDetail(link: ExceptionLinkLike): WhyDetail {
  const identity = resolveClauseIdentity(link)
  const lines: string[] = []
  const signal = (link.signal_type || '').trim()
  const rationale = link.rationale?.trim() ?? ''
  const notes = link.notes?.trim() ?? ''
  const generic = isGenericRationale(rationale)

  lines.push(
    `${identity.schemeLabel} · clause ${identity.clauseNumber}${
      identity.clauseTitle ? ` — ${identity.clauseTitle}` : ''
    }`,
  )
  if (identity.sectionPath) lines.push(`Section path: ${identity.sectionPath}`)
  if (signal) lines.push(`Signal: ${signal.replace(/_/g, ' ')}`)
  if (link.confidence != null) {
    lines.push(`AI confidence: ${Math.round(link.confidence * 100)}%`)
  }
  if (link.linked_by) lines.push(`Linked by: ${link.linked_by}`)

  if (rationale && !generic) {
    lines.push(`Why: ${rationale}`)
  } else if (notes) {
    lines.push(`Assessment note: ${notes}`)
  } else if (link.title && !isGenericRationale(link.title)) {
    lines.push(`Why: ${link.title}`)
  } else if (generic && rationale) {
    lines.push(
      `AI supplied only a generic label (“${rationale}”) — open the source and compare against ${identity.schemeLabel} clause ${identity.clauseNumber}.`,
    )
  } else {
    lines.push(
      `No specific mapping reason recorded — review the ${link.entity_type.replace(/_/g, ' ')} source against ${identity.schemeLabel} clause ${identity.clauseNumber}.`,
    )
  }

  const summary = lines.find((line) => line.startsWith('Why:'))?.slice(5).trim()
    ?? lines.find((line) => line.startsWith('Assessment note:'))?.slice(18).trim()
    ?? lines[lines.length - 1]

  return { summary, lines, isGeneric: generic }
}
