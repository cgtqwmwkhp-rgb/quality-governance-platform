/** Incident detail tabs — Standards host parity with Near Miss + URL deeplink. */
export const INCIDENT_DETAIL_TABS = [
  'overview',
  'standards',
  'submission',
  'witnesses',
  'photos',
  'running-sheet',
] as const

export type IncidentDetailTab = (typeof INCIDENT_DETAIL_TABS)[number]

export function resolveIncidentDetailTab(
  raw: string | null | undefined,
): IncidentDetailTab {
  if (raw && (INCIDENT_DETAIL_TABS as readonly string[]).includes(raw)) {
    return raw as IncidentDetailTab
  }
  return 'overview'
}

/** Deep-link into Standards tab (Near Miss / Exceptions closed-loop parity). */
export function incidentStandardsHref(id: string | number): string {
  return `/incidents/${id}?tab=standards`
}
