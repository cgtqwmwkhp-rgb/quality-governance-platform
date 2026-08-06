/**
 * Pure eligibility helpers for the Incident → FRA significant-change prompt.
 * Mirrors backend policy in `incident_fra_review.py`.
 */

export const FRA_SIGNIFICANT_TYPES = new Set(['property_damage', 'hazard'])
export const FRA_SIGNIFICANT_SEVERITIES = new Set(['high', 'critical'])
export const FIRE_EMERGENCY_CODE = 'fire'

export const FRA_SIGCHANGE_DISMISS_PREFIX = 'incident_fra_sigchange_dismissed_'

export type FraSignificantChangeIncident = {
  id?: number
  status?: string | null
  emergency_services?: string[] | null
  incident_type?: string | null
  severity?: string | null
  is_sif?: boolean | null
  is_psif?: boolean | null
}

function norm(value?: string | null): string {
  return (value ?? '').trim().toLowerCase()
}

/** True when the incident signals a premises significant change for FRA review. */
export function incidentSuggestsFraSignificantChange(
  incident: FraSignificantChangeIncident | null | undefined,
): boolean {
  if (!incident) return false

  const services = incident.emergency_services ?? []
  if (services.some((code) => norm(String(code)) === FIRE_EMERGENCY_CODE)) {
    return true
  }

  const type = norm(incident.incident_type)
  const severity = norm(incident.severity)
  if (FRA_SIGNIFICANT_TYPES.has(type) && FRA_SIGNIFICANT_SEVERITIES.has(severity)) {
    return true
  }

  if (incident.is_sif || incident.is_psif) {
    return true
  }

  return false
}

export function fraSignificantChangeDismissKey(incidentId: number): string {
  return `${FRA_SIGCHANGE_DISMISS_PREFIX}${incidentId}`
}

export function isFraSignificantChangeDismissed(incidentId: number): boolean {
  try {
    return localStorage.getItem(fraSignificantChangeDismissKey(incidentId)) === '1'
  } catch {
    return false
  }
}

export function dismissFraSignificantChange(incidentId: number): void {
  try {
    localStorage.setItem(fraSignificantChangeDismissKey(incidentId), '1')
  } catch {
    // localStorage unavailable — dismiss is best-effort for the session only
  }
}

export function clearFraSignificantChangeDismiss(incidentId: number): void {
  try {
    localStorage.removeItem(fraSignificantChangeDismissKey(incidentId))
  } catch {
    // ignore
  }
}

/**
 * Whether the Incident Detail panel should render.
 * Requires CS flag, closed status, eligibility, and not dismissed.
 */
export function shouldShowFraSignificantChangePrompt(
  incident: FraSignificantChangeIncident | null | undefined,
  options: { flagEnabled: boolean; dismissed?: boolean },
): boolean {
  if (!options.flagEnabled || !incident) return false
  if (norm(incident.status) !== 'closed') return false
  if (!incidentSuggestsFraSignificantChange(incident)) return false
  const dismissed =
    options.dismissed ??
    (typeof incident.id === 'number' ? isFraSignificantChangeDismissed(incident.id) : false)
  return !dismissed
}
