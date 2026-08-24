/**
 * The one date format used on the Front Sheet.
 *
 * `en-GB` explicitly rather than the ambient locale: a governance date read off
 * a cover sheet — effective, next review, disposal — must not change shape with
 * the reader's browser, because a screenshot of it is evidence.
 */
export function formatLibraryDate(raw: string | null | undefined): string | null {
  const value = (raw ?? '').trim()
  if (!value) return null
  const parsed = new Date(value)
  // An unparseable value is shown as stored. "Invalid Date" would tell the
  // reader nothing about what the register actually holds.
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
