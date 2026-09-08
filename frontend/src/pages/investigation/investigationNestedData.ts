/**
 * Nested / flat investigation JSON for the workspace page (INV-C4).
 *
 * Creation from a template run stores `data.sections.<section>.<field>`; this page has always
 * written flat keys (`data.findings`). The report path only walks `data.sections`, so a finding
 * typed here never reached the pack, and a finding that arrived nested never appeared in these
 * editors.
 *
 * Reads mirror the server-side C3 reader: the nested value for the field's own section wins, and
 * the flat key is the fallback. Writes are dual — the typed value goes to the flat key *and* to
 * the nested section, so an edit cannot be masked by the stale copy in the other shape. Flat keys
 * are never removed; that contraction is C18.
 */

export const FINDINGS_SECTION = 'section_3_investigation_findings'
export const ROOT_CAUSE_SECTION = 'section_4_root_cause'
/** The default template (id=1) declares its root-cause section as `rca`. */
export const LEGACY_RCA_SECTION = 'rca'

const FINDINGS_SECTIONS = [FINDINGS_SECTION] as const
const ROOT_CAUSE_SECTIONS = [ROOT_CAUSE_SECTION, LEGACY_RCA_SECTION] as const

export const WORKSPACE_FIELD_SECTIONS: Record<string, readonly string[]> = {
  lead_investigator: FINDINGS_SECTIONS,
  findings: FINDINGS_SECTIONS,
  conclusion: FINDINGS_SECTIONS,
  problem_statement: ROOT_CAUSE_SECTIONS,
  root_cause: ROOT_CAUSE_SECTIONS,
  contributing_factors: ROOT_CAUSE_SECTIONS,
  why_1: ROOT_CAUSE_SECTIONS,
  why_2: ROOT_CAUSE_SECTIONS,
  why_3: ROOT_CAUSE_SECTIONS,
  why_4: ROOT_CAUSE_SECTIONS,
  why_5: ROOT_CAUSE_SECTIONS,
}

type InvestigationData = Record<string, unknown>

function asRecord(value: unknown): InvestigationData | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as InvestigationData
}

/** The section map, or null when `sections` is absent, list-shaped, or malformed. */
function sectionMap(data: InvestigationData | null): InvestigationData | null {
  if (!data) return null
  return asRecord(data.sections)
}

function sectionsFor(field: string): readonly string[] {
  return WORKSPACE_FIELD_SECTIONS[field] ?? []
}

/**
 * Read a workspace text field, nested value first.
 *
 * Only a nested *string* can win: a checklist array or an object belongs to the structured
 * editors, and rendering it here would let a save flatten it into `[object Object]`.
 */
export function readWorkspaceText(data: unknown, field: string): string {
  const blob = asRecord(data)
  const sections = sectionMap(blob)

  if (sections) {
    for (const sectionKey of sectionsFor(field)) {
      const value = asRecord(sections[sectionKey])?.[field]
      if (typeof value === 'string' && value.trim() !== '') return value
    }
  }

  const flat = blob?.[field]
  if (flat === null || flat === undefined) return ''
  return typeof flat === 'string' ? flat : String(flat)
}

/**
 * Return `data` with each update written to its flat key and to its nested section(s).
 *
 * Other keys and other sections are carried over untouched. A list-shaped `sections` payload is
 * left alone — the server merge owns that shape, and rewriting it here would corrupt it. A nested
 * slot that currently holds an array or object is also left alone, so text cannot overwrite a
 * structured answer.
 */
export function withWorkspaceFields(
  data: unknown,
  updates: Record<string, string>,
): InvestigationData {
  const merged: InvestigationData = { ...(asRecord(data) ?? {}) }
  for (const [field, value] of Object.entries(updates)) {
    merged[field] = value
  }

  const existingSections = sectionMap(merged)
  if (!existingSections && merged.sections !== undefined && merged.sections !== null) {
    return merged
  }

  const sections: InvestigationData = { ...(existingSections ?? {}) }
  let touched = false

  for (const [field, value] of Object.entries(updates)) {
    for (const sectionKey of sectionsFor(field)) {
      const current = asRecord(sections[sectionKey])
      if (sections[sectionKey] !== undefined && current === null) continue

      const slot = current?.[field]
      const slotExists = current !== null && slot !== undefined
      if (slotExists && slot !== null && typeof slot !== 'string') continue
      if (!slotExists && value.trim() === '') continue

      sections[sectionKey] = { ...(current ?? {}), [field]: value }
      touched = true
    }
  }

  if (touched) merged.sections = sections
  return merged
}
