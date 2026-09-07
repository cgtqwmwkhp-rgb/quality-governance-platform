/**
 * Evidence tab queries. Source-record files are linked via
 * linked_investigation_id (source_module stays incident/near_miss/…). Files
 * uploaded on the investigation itself use source_module=investigation and
 * often have no link column. The list API ANDs filters, so both queries are
 * required; merging by id is how both sets appear on one tab.
 */

export const INVESTIGATION_EVIDENCE_PAGE_SIZE = 50

export function investigationNativeEvidenceParams(investigationId: number) {
  return {
    source_module: 'investigation' as const,
    source_id: investigationId,
    page: 1,
    page_size: INVESTIGATION_EVIDENCE_PAGE_SIZE,
  }
}

export function investigationLinkedEvidenceParams(investigationId: number) {
  return {
    linked_investigation_id: investigationId,
    page: 1,
    page_size: INVESTIGATION_EVIDENCE_PAGE_SIZE,
  }
}

export function mergeEvidenceAssetsById<T extends { id: number }>(groups: T[][]): T[] {
  const byId = new Map<number, T>()
  for (const group of groups) {
    for (const item of group) {
      if (!byId.has(item.id)) byId.set(item.id, item)
    }
  }
  return [...byId.values()]
}
