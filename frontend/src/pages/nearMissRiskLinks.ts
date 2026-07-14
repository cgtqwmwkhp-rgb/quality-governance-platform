/** Parse comma-separated near-miss linked_risk_ids into unique numbers. */
export function parseLinkedRiskIds(raw?: string | null): number[] {
  if (!raw) return []
  const seen = new Set<number>()
  const ids: number[] = []
  for (const part of raw.split(',')) {
    const value = Number(part.trim())
    if (!Number.isInteger(value) || value <= 0 || seen.has(value)) continue
    seen.add(value)
    ids.push(value)
  }
  return ids
}

/** Enterprise Risk Register deep link (canonical UI). */
export function riskRegisterHref(
  riskId: number,
  options?: { nearMissRef?: string | null },
): string {
  const params = new URLSearchParams()
  params.set('riskId', String(riskId))
  if (options?.nearMissRef) params.set('nearMissRef', options.nearMissRef)
  return `/risk-register?${params.toString()}`
}
