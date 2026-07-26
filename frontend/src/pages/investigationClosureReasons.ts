/**
 * Human-readable closure blockers for the investigation closure checklist.
 *
 * The checklist used to render reason codes raw ("MISSING REQUIRED SECTION"),
 * which told the user nothing about *which* section was incomplete. The API now
 * returns `missing_items` naming each blocking section/field, so a reason code
 * that has named items is expanded into one line per item.
 */
import type { ClosureMissingItem, ClosureValidation } from '../api/investigationsClient'

/** Translator shape compatible with i18next's `t(key, defaultValue, options)`. */
export type ClosureTranslate = (
  key: string,
  defaultValue: string,
  options?: Record<string, unknown>,
) => string

export interface ClosureBlockerLine {
  /** Stable React key. */
  id: string
  /** Reason code this line was derived from. */
  code: string
  /** Sentence shown to the user. */
  text: string
  /** Section key when the blocker is tied to a template section. */
  sectionKey?: string
}

/** Reason codes that `missing_items` can name. */
const NAMEABLE_CODES = new Set([
  'MISSING_REQUIRED_SECTION',
  'MISSING_REQUIRED_FIELD',
  'INVALID_ARRAY_EMPTY',
  'LEAD_INVESTIGATOR_NOT_ASSIGNED',
  'INVESTIGATION_NOT_STARTED',
  'MISSING_FINDINGS',
  'MISSING_CONCLUSION',
])

function describeItem(item: ClosureMissingItem, t: ClosureTranslate): string {
  const section = item.section_label || item.section_key
  const fieldLabel = item.field_label || item.field_key

  if (item.code === 'MISSING_REQUIRED_SECTION' || !fieldLabel) {
    return t(
      'investigations.closure.missing_section_named',
      '"{{section}}" has not been completed. Fill in its required answers, then re-check.',
      { section },
    )
  }
  if (item.code === 'INVALID_ARRAY_EMPTY') {
    return t(
      'investigations.closure.empty_list_named',
      '"{{field}}" in "{{section}}" needs at least one entry.',
      { field: fieldLabel, section },
    )
  }
  return t(
    'investigations.closure.missing_field_named',
    '"{{field}}" in "{{section}}" is required and has not been answered.',
    { field: fieldLabel, section },
  )
}

function describeCode(code: string, t: ClosureTranslate): string {
  switch (code) {
    case 'OPEN_ACTIONS_REMAIN':
      return t(
        'investigations.closure.open_actions_remain',
        'Open CAPA/actions must be completed or cancelled before closure.',
      )
    case 'LEVEL_NOT_SET':
      return t(
        'investigations.closure.level_not_set',
        'Set the investigation level before closing.',
      )
    case 'STATUS_NOT_COMPLETE':
      return t(
        'investigations.closure.status_not_complete',
        'Move the investigation to Completed before closing.',
      )
    case 'LEAD_INVESTIGATOR_NOT_ASSIGNED':
      return t(
        'investigations.closure.lead_not_assigned',
        'Assign a lead investigator on the Summary tab before completing.',
      )
    case 'INVESTIGATION_NOT_STARTED':
      return t(
        'investigations.closure.not_started',
        'Move the investigation to In progress before completing.',
      )
    case 'MISSING_FINDINGS':
      return t(
        'investigations.closure.missing_findings',
        'Record investigation findings on the Summary tab before completing.',
      )
    case 'MISSING_CONCLUSION':
      return t(
        'investigations.closure.missing_conclusion',
        'Record a conclusion on the Summary tab before completing.',
      )
    case 'TEMPLATE_NOT_FOUND':
      return t(
        'investigations.closure.template_not_found',
        'The investigation template could not be loaded, so closure cannot be verified.',
      )
    case 'MISSING_REQUIRED_SECTION':
      return t(
        'investigations.closure.missing_section_unnamed',
        'A required template section has not been completed. Re-check to load the section name.',
      )
    case 'MISSING_REQUIRED_FIELD':
      return t(
        'investigations.closure.missing_field_unnamed',
        'A required template answer is missing. Re-check to load the field name.',
      )
    case 'INVALID_ARRAY_EMPTY':
      return t(
        'investigations.closure.empty_list_unnamed',
        'A required list is empty. Re-check to load the field name.',
      )
    default:
      // Unknown codes are still surfaced, but not shouted in raw SCREAMING_CASE.
      return code.replace(/_/g, ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase())
  }
}

/**
 * Turn `reasons` + `missing_items` into named, ordered lines for display.
 *
 * Reason-code order is preserved so the list stays stable between polls.
 */
export function describeClosureBlockers(
  validation: Pick<ClosureValidation, 'reasons' | 'missing_items'>,
  t: ClosureTranslate,
): ClosureBlockerLine[] {
  const items = validation.missing_items ?? []
  const lines: ClosureBlockerLine[] = []
  const seen = new Set<string>()

  for (const code of validation.reasons ?? []) {
    const named = NAMEABLE_CODES.has(code) ? items.filter((item) => item.code === code) : []

    if (named.length === 0) {
      const id = `code:${code}`
      if (seen.has(id)) continue
      seen.add(id)
      lines.push({ id, code, text: describeCode(code, t) })
      continue
    }

    for (const item of named) {
      const id = `${code}:${item.path}`
      if (seen.has(id)) continue
      seen.add(id)
      lines.push({
        id,
        code,
        text: describeItem(item, t),
        sectionKey: item.section_key,
      })
    }
  }

  return lines
}

export function describeCompletionBlockers(
  validation: Pick<ClosureValidation, 'completion_reasons' | 'missing_items'>,
  t: ClosureTranslate,
): ClosureBlockerLine[] {
  return describeClosureBlockers(
    {
      reasons: validation.completion_reasons ?? [],
      missing_items: validation.missing_items,
    },
    t,
  )
}

export function isOnlyOpenActionsBlocking(reasons: string[] | undefined): boolean {
  const list = reasons ?? []
  return list.length === 1 && list[0] === 'OPEN_ACTIONS_REMAIN'
}
