/** Evaluate FormField / FormStep `show_condition` JSON against current values. */

export function fieldMatchesShowCondition(
  condition: Record<string, unknown> | undefined | null,
  formData: Record<string, unknown>,
): boolean {
  if (!condition || Object.keys(condition).length === 0) return true

  const field = typeof condition.field === 'string' ? condition.field : undefined
  if (field) {
    const actual = formData[field]
    if ('equals' in condition) return actual === condition.equals
    if ('not_equals' in condition) return actual !== condition.not_equals
    if (Array.isArray(condition.in)) return condition.in.includes(actual)
  }

  return Object.entries(condition).every(([key, expected]) => {
    if (key === 'field' || key === 'equals' || key === 'not_equals' || key === 'in') return true
    return formData[key] === expected
  })
}
