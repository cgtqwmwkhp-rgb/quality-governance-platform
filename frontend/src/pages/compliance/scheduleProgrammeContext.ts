/**
 * Programme (Evidence Workspace) → Compliance Schedule SoR.
 *
 * Deep-link only. Never a second obligation register, never a cell-aggregate fork.
 */

export function scheduleProgrammeHref(
  frameworkId?: string | null,
  clauseNumber?: string | null,
): string {
  const params = new URLSearchParams()
  const clause = clauseNumber?.trim()
  const framework = frameworkId?.trim()
  if (clause) params.set('clause', clause)
  if (framework) params.set('framework', framework)
  const qs = params.toString()
  return qs ? `/compliance-schedule?${qs}` : '/compliance-schedule'
}

export function obligationMentionsClause(
  item: {
    title?: string | null
    description?: string | null
    regulatory_basis?: string | null
    reference_number?: string | null
  },
  clause: string,
): boolean {
  const needle = clause.trim().toLowerCase()
  if (!needle) return false
  const hay = [item.title, item.description, item.regulatory_basis, item.reference_number]
    .filter((v): v is string => Boolean(v && v.trim()))
    .join('\n')
    .toLowerCase()
  return hay.includes(needle)
}
