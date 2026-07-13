/** Complaint detail tabs — mirrors Near Miss Standards host pattern + URL deeplink. */
export const COMPLAINT_DETAIL_TABS = [
  'overview',
  'standards',
  'submission',
  'running-sheet',
] as const

export type ComplaintDetailTab = (typeof COMPLAINT_DETAIL_TABS)[number]

export function resolveComplaintDetailTab(
  raw: string | null | undefined,
): ComplaintDetailTab {
  if (raw && (COMPLAINT_DETAIL_TABS as readonly string[]).includes(raw)) {
    return raw as ComplaintDetailTab
  }
  return 'overview'
}

/** Deep-link into Standards tab (Near Miss / Exceptions closed-loop parity). */
export function complaintStandardsHref(id: string | number): string {
  return `/complaints/${id}?tab=standards`
}
