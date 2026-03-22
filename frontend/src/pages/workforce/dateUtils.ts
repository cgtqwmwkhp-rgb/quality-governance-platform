export function parseScheduledLocalDate(value?: string): Date | null {
  if (!value) return null

  const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (dateOnlyMatch) {
    const [, year, month, day] = dateOnlyMatch
    return new Date(Number(year), Number(month) - 1, Number(day))
  }

  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatScheduledDate(value?: string): string {
  const parsed = parseScheduledLocalDate(value)
  return parsed ? parsed.toLocaleDateString() : '—'
}
