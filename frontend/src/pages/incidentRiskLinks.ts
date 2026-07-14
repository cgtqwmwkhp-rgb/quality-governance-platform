/** Parse comma-separated incident linked_risk_ids into unique numbers. */
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
  options?: { incidentRef?: string | null },
): string {
  const params = new URLSearchParams()
  params.set('riskId', String(riskId))
  if (options?.incidentRef) params.set('incidentRef', options.incidentRef)
  return `/risk-register?${params.toString()}`
}

/** Severities eligible for guided raise-risk (mirrors backend policy). */
export const RAISE_RISK_ALLOWED_SEVERITIES = new Set(['high', 'critical'])

export function severityAllowsRaiseRisk(severity?: string | null): boolean {
  if (!severity) return false
  return RAISE_RISK_ALLOWED_SEVERITIES.has(severity.trim().toLowerCase())
}
