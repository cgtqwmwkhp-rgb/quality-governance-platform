/**
 * Presentation layer for coded values.
 *
 * Backend enums, database column names, permission codes and surrogate keys are data.
 * They are not display strings. Everything that renders one of those to a user goes
 * through this module so the vocabulary lives in one place instead of being re-derived
 * with an ad-hoc `.replace(/_/g, ' ')` on every page.
 *
 * These functions are deliberately pure and i18n-free: they turn a code into a readable
 * label deterministically, including for values nobody has enumerated yet. Copy that a
 * human wrote belongs in the locale files, not here.
 */

/** Words that must not be sentence-cased into something unreadable. */
const ACRONYMS = new Set([
  'AFR',
  'CAPA',
  'CDM',
  'COSHH',
  'FTE',
  'HSE',
  'HSEQ',
  'HSG245',
  'ICS',
  'ID',
  'IMS',
  'ISO',
  'KPI',
  'LTI',
  'MFA',
  'PPE',
  'RIDDOR',
  'ROSPA',
  'RTA',
  'SLA',
  'SOA',
  'URL',
  'UVDB',
  'VIN',
])

/**
 * Values whose mechanical label would be wrong or ambiguous.
 * Keys are normalised (lowercase, separators collapsed to underscore).
 */
const CODED_VALUE_OVERRIDES: Record<string, string> = {
  awaiting_customer: 'Awaiting customer response',
  ces_import: 'Imported reference data',
  near_miss: 'Near miss',
  object_strike: 'Struck a stationary object',
  pending_response: 'Awaiting our response',
  rear_end: 'Rear-end collision',
  side_impact: 'Side impact',
  single_vehicle: 'Single vehicle',
  under_investigation: 'Under investigation',
  actions_in_progress: 'Actions in progress',
  pending_actions: 'Pending actions',
  pending_review: 'Pending review',
}

/**
 * Database column and settings-key names that stay jargon even after mechanical
 * formatting. Anything not listed here is formatted by rule.
 */
const FIELD_NAME_OVERRIDES: Record<string, string> = {
  external_id: 'External reference',
  job_title: 'Job title',
  next_review_date: 'Review due date',
  reference_number: 'Reference',
  role_key: 'Workforce role',
  tenant_id: 'Organisation',
}

/** Permission codes we have plain-English wording for. */
const PERMISSION_OVERRIDES: Record<string, string> = {
  'investigation:approve_customer_omit':
    'Approve leaving a section out of the customer pack',
}

/**
 * `ComplaintStatus.ACKNOWLEDGED` — a Python enum member rendered by an f-string.
 * The class part must be multi-hump CamelCase so that ordinary text such as
 * `Report.PDF` is left alone.
 */
const PYTHON_ENUM_REPR = /\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\.([A-Z][A-Z0-9_]*)\b/g

/** A single-quoted coded token inside a sentence, e.g. `'under_investigation'`. */
const QUOTED_CODED_TOKEN = /'([a-z][a-z0-9]*(?:_[a-z0-9]+)*)'/g

/** A bare SCREAMING_SNAKE token, e.g. `NEAR_MISS`. Requires a separator to avoid acronyms. */
const BARE_SCREAMING_SNAKE = /\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** A hex digest. Must contain a hex letter, so a long numeric serial is not swallowed. */
const HEX_DIGEST = /^(?=[0-9]*[a-f])[0-9a-f]{24,}$/i

function normaliseKey(value: string): string {
  return value.trim().toLowerCase().replace(/[\s\-:/.]+/g, '_')
}

/**
 * A token is safe to reformat only if it is recognisably a code. A mixed-case token with
 * no separator (`Report.PDF`, `v11.8`) is something a human already wrote, and
 * sentence-casing it would destroy information.
 *
 * camelCase is treated as a code, so a brand name of that shape would be split. That is
 * the deliberate trade: `daysLost` must become `Days lost`, and the two are the same shape.
 */
function looksCoded(token: string): boolean {
  if (/[_\-:/]/.test(token)) return true
  if (/^[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+$/.test(token)) return true
  return /^[a-z0-9]+$/.test(token) || /^[A-Z0-9]+$/.test(token)
}

function splitWords(value: string): string[] {
  return value
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_\-:/]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
}

function sentenceCase(words: string[]): string {
  return words
    .map((word, index) => {
      const upper = word.toUpperCase()
      if (ACRONYMS.has(upper)) return upper
      const lower = word.toLowerCase()
      return index === 0 ? lower.charAt(0).toUpperCase() + lower.slice(1) : lower
    })
    .join(' ')
}

/** Shared core: override lookup, then mechanical formatting when the token is a code. */
function humaniseToken(token: string, overrides: Record<string, string>): string {
  const override = overrides[normaliseKey(token)]
  if (override) return override
  if (!looksCoded(token)) return token

  const words = splitWords(token)
  if (words.length === 0) return token
  return sentenceCase(words)
}

/**
 * Turn a coded value into a label a user can read.
 *
 * Handles snake_case, SCREAMING_SNAKE, kebab-case, camelCase and Python enum reprs
 * (`ComplaintStatus.ACKNOWLEDGED`). Values that already contain whitespace are treated
 * as free text and returned untouched — `collision_type` and friends are free-text
 * columns, so a real sentence typed by a user must survive this function intact.
 */
export function formatCodedValue(value: string | null | undefined): string {
  if (value === null || value === undefined) return ''
  const trimmed = String(value).trim()
  if (!trimmed) return ''
  if (/\s/.test(trimmed)) return trimmed

  const enumRepr = trimmed.match(/^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\.([A-Z][A-Z0-9_]*)$/)
  const token = enumRepr ? enumRepr[1] : trimmed

  return humaniseToken(token, CODED_VALUE_OVERRIDES)
}

/**
 * Turn a database column or settings key into a field label.
 *
 * Use this wherever a key such as `company_logo_url` would otherwise be rendered
 * beside or instead of a human label.
 */
export function formatFieldName(key: string | null | undefined): string {
  if (key === null || key === undefined) return ''
  const trimmed = String(key).trim()
  if (!trimmed) return ''

  return humaniseToken(trimmed, FIELD_NAME_OVERRIDES)
}

/**
 * Turn a permission code such as `investigation:approve_customer_omit` into a phrase
 * describing what the permission lets someone do.
 */
export function formatPermissionCode(code: string | null | undefined): string {
  if (code === null || code === undefined) return ''
  const trimmed = String(code).trim()
  if (!trimmed) return ''

  const override = PERMISSION_OVERRIDES[trimmed.toLowerCase()]
  if (override) return override

  const [domain, ...rest] = trimmed.split(':')
  const action = rest.join(':')
  if (!action) return formatCodedValue(domain)
  return `${formatCodedValue(action)} (${formatCodedValue(domain)})`
}

/**
 * Strip coded tokens out of a message that was composed elsewhere — typically a server
 * error surfaced in a toast.
 *
 * Quoted single words are sentence-cased too, which is why this must only be applied to
 * machine-generated messages: it would capitalise a user's own input if that input were
 * echoed back in quotes.
 */
export function humaniseCodedText(text: string | null | undefined): string {
  if (text === null || text === undefined) return ''
  const trimmed = String(text)
  if (!trimmed) return ''

  return trimmed
    .replace(PYTHON_ENUM_REPR, (_match, member: string) => formatCodedValue(member))
    .replace(QUOTED_CODED_TOKEN, (_match, token: string) => `'${formatCodedValue(token)}'`)
    .replace(BARE_SCREAMING_SNAKE, (match) => formatCodedValue(match))
}

/**
 * True when a value is a surrogate key with no meaning to a user — a generated UUID or
 * a long hex blob. Such values should not be rendered on a record.
 */
export function isOpaqueIdentifier(value: string | null | undefined): boolean {
  if (value === null || value === undefined) return false
  const trimmed = String(value).trim()
  if (!trimmed) return false
  return UUID.test(trimmed) || HEX_DIGEST.test(trimmed)
}
