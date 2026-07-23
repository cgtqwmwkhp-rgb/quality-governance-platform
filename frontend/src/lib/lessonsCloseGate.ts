/** Soft close gate: warn when closing without lessons; never hard-block. */

export function confirmCloseWithoutLessons(params: {
  nextStatus?: string | null
  previousStatus?: string | null
  lessons?: string | null
}): boolean {
  const next = (params.nextStatus || '').toLowerCase()
  const prev = (params.previousStatus || '').toLowerCase()
  const closing = next === 'closed' && prev !== 'closed'
  if (!closing) return true
  if ((params.lessons || '').trim()) return true
  return window.confirm(
    'No lessons learnt recorded. Close anyway? You can add lessons later on the case record.',
  )
}
