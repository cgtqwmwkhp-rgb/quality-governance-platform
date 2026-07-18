/**
 * Detail-lane API helpers (avoid colliding with InvList investigationsClient edits).
 */
import api from '../../api/client'

export type CustomerPackVisibilityMeta = {
  omit_requested?: boolean
  omit_approved?: boolean
  omit_reason?: string | null
  omit_requested_by?: number | null
  omit_approved_by?: number | null
  omit_approved_at?: string | null
}

export async function addManualTimelineEntry(investigationId: number, content: string) {
  return api.post(`/api/v1/investigations/${investigationId}/timeline`, { content })
}

export async function requestCustomerPackOmit(
  investigationId: number,
  sectionId: string,
  omitRequested: boolean,
  reason?: string,
) {
  return api.post(`/api/v1/investigations/${investigationId}/customer-pack-omit`, {
    section_id: sectionId,
    omit_requested: omitRequested,
    reason,
  })
}

export async function approveCustomerPackOmit(
  investigationId: number,
  sectionId: string,
  reason?: string,
) {
  return api.post(`/api/v1/investigations/${investigationId}/customer-pack-omit/approve`, {
    section_id: sectionId,
    reason,
  })
}

export async function updateEvidenceVisibility(assetId: number, visibility: string) {
  return api.patch(`/api/v1/evidence-assets/${assetId}`, { visibility })
}

export function readCustomerPackVisibility(
  data: Record<string, unknown> | null | undefined,
): Record<string, CustomerPackVisibilityMeta> {
  const raw = data?.customer_pack_visibility
  if (!raw || typeof raw !== 'object') return {}
  return raw as Record<string, CustomerPackVisibilityMeta>
}
