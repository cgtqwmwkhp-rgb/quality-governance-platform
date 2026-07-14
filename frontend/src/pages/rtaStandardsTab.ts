/** RTA detail tabs — Standards host parity with Near Miss + URL deeplink. */
export const RTA_DETAIL_TABS = [
  'overview',
  'standards',
  'submission',
  'vehicle1',
  'vehicle2',
  'driver1',
  'driver2',
  'witnesses',
  'photos',
  'running-sheet',
  'actions',
] as const

export type RtaDetailTab = (typeof RTA_DETAIL_TABS)[number]

export function resolveRtaDetailTab(raw: string | null | undefined): RtaDetailTab {
  if (raw && (RTA_DETAIL_TABS as readonly string[]).includes(raw)) {
    return raw as RtaDetailTab
  }
  return 'overview'
}

/** Deep-link into Standards tab (Near Miss / Exceptions closed-loop parity). */
export function rtaStandardsHref(id: string | number): string {
  return `/rtas/${id}?tab=standards`
}
