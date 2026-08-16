/** Purpose identity for Audit & Assessment Builder templates (N-BUILD-1). */

export const INSTRUMENT_KINDS = ['audit', 'skills', 'induction'] as const
export type InstrumentKind = (typeof INSTRUMENT_KINDS)[number]

export const INSTRUMENT_TAG_PREFIX = 'instrument:'

export function instrumentTag(kind: InstrumentKind): string {
  return `${INSTRUMENT_TAG_PREFIX}${kind}`
}

function isInstrumentKind(value: string): value is InstrumentKind {
  return (INSTRUMENT_KINDS as readonly string[]).includes(value)
}

/** URL `?instrument=` — only the three purposes; otherwise null (do not default). */
export function parseInstrumentQuery(value: string | null | undefined): InstrumentKind | null {
  if (!value) return null
  const normalised = value.trim().toLowerCase()
  return isInstrumentKind(normalised) ? normalised : null
}

/** First `instrument:*` tag, or null when untagged. */
export function parseInstrumentTag(tags: string[] | null | undefined): InstrumentKind | null {
  if (!tags) return null
  for (const tag of tags) {
    if (typeof tag !== 'string') continue
    const trimmed = tag.trim()
    if (!trimmed.startsWith(INSTRUMENT_TAG_PREFIX)) continue
    const kind = trimmed.slice(INSTRUMENT_TAG_PREFIX.length).toLowerCase()
    if (isInstrumentKind(kind)) return kind
  }
  return null
}

/** Untagged LIVE templates default to Audit. */
export function parseInstrument(tags: string[] | null | undefined): InstrumentKind {
  return parseInstrumentTag(tags) ?? 'audit'
}

/** Client-side purpose filter for create/schedule pickers (N-BUILD-2). */
export function templatesMatchingInstrument<T extends { tags?: string[] | null }>(
  items: T[],
  kind: InstrumentKind,
): T[] {
  return items.filter((item) => parseInstrument(item.tags) === kind)
}

/** Replace any `instrument:*` tag; keep builder_brief / source_case / other tags. */
export function upsertInstrumentTag(
  tags: string[] | null | undefined,
  kind: InstrumentKind,
): string[] {
  const kept = (tags ?? []).filter(
    (tag) => typeof tag === 'string' && !tag.trim().toLowerCase().startsWith(INSTRUMENT_TAG_PREFIX),
  )
  kept.push(instrumentTag(kind))
  return kept
}

export function instrumentRunHref(kind: InstrumentKind, templateId: number): string {
  switch (kind) {
    case 'skills':
      return `/workforce/assessments/new?templateId=${templateId}`
    case 'induction':
      return `/workforce/training/new?templateId=${templateId}`
    default:
      return `/audits?templateId=${templateId}`
  }
}

/** Existing workforce calendar — not a builder-owned scheduler (N-BUILD-3). */
export const TRAINING_CALENDAR_HREF = '/calendar?types=training'

/** Skills and induction cadence lives on /calendar?types=training. Audits stay on Schedule. */
export function instrumentCalendarHref(kind: InstrumentKind): string | null {
  if (kind === 'skills' || kind === 'induction') return TRAINING_CALENDAR_HREF
  return null
}

export function instrumentCtaKey(kind: InstrumentKind): string {
  switch (kind) {
    case 'skills':
      return 'audit_builder.cta.start_skills'
    case 'induction':
      return 'audit_builder.cta.start_induction'
    default:
      return 'audit_builder.cta.schedule_audit'
  }
}
