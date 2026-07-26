import { formatDisplayDate } from '../helpers/formatters'

/** ISO date (YYYY-MM-DD) that UAT saw leaked into notification copy (PX-187). */
const ISO_DATE = /\b(\d{4}-\d{2}-\d{2})\b/g

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

/** Absolute list stamp: prefer UK date over locale-default toLocaleDateString. */
export function formatNotificationListDate(iso: string): string {
  return formatDisplayDate(iso)
}
