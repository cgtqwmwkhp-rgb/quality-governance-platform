import { formatCodedValue } from '../helpers/displayLabels'
import { formatDisplayDate } from '../helpers/formatters'

/** ISO date (YYYY-MM-DD) that UAT saw leaked into notification copy (PX-187). */
const ISO_DATE = /\b(\d{4}-\d{2}-\d{2})\b/g

/**
 * Known governance acronyms that must stay fully uppercase when they appear as
 * whole words in notification titles / body copy (PX-188).
 *
 * Kept local so this helper stays free of new i18n keys; casing only.
 */
const NOTIFICATION_ACRONYMS = new Set([
  'afr',
  'capa',
  'cdm',
  'coshh',
  'fte',
  'hse',
  'hseq',
  'hsg245',
  'ics',
  'ims',
  'iso',
  'kpi',
  'lti',
  'mfa',
  'ncr',
  'ppe',
  'riddor',
  'rospa',
  'rta',
  'sla',
  'soa',
  'uvdb',
  'vin',
])

/** Whole-word token match for acronym rewrite (case-insensitive). */
const ACRONYM_WORD = /\b([A-Za-z][A-Za-z0-9]*)\b/g

/**
 * Rewrite bare ISO calendar dates in notification body text to UK DD/MM/YYYY.
 * Leaves timestamps with time components alone (handled by formatDisplayDateTime callers).
 */
export function rewriteIsoDatesInNotificationText(text: string): string {
  if (!text) return text
  return text.replace(ISO_DATE, (match) => {
    const formatted = formatDisplayDate(match)
    return formatted === '—' ? match : formatted
  })
}

/**
 * Uppercase known acronyms that appear as whole words so "New rta assigned to you"
 * renders as "New RTA assigned to you" (PX-188). Ordinary words are left alone.
 */
export function rewriteAcronymsInNotificationText(text: string): string {
  if (!text) return text
  return text.replace(ACRONYM_WORD, (word) => {
    const key = word.toLowerCase()
    return NOTIFICATION_ACRONYMS.has(key) ? key.toUpperCase() : word
  })
}

/** Dates + acronym casing for titles and messages shown on /notifications. */
export function formatNotificationDisplayText(text: string): string {
  return rewriteAcronymsInNotificationText(rewriteIsoDatesInNotificationText(text))
}

/**
 * Entity-type chip label: `rta` → `RTA`, `near_miss` → readable label.
 * Uses the shared coded-value formatter so vocabulary stays consistent.
 */
export function formatNotificationEntityLabel(
  entityType?: string | null,
): string | undefined {
  if (!entityType) return undefined
  const label = formatCodedValue(entityType)
  return label || undefined
}

/** Absolute list stamp: prefer UK date over locale-default toLocaleDateString. */
export function formatNotificationListDate(iso: string): string {
  return formatDisplayDate(iso)
}
