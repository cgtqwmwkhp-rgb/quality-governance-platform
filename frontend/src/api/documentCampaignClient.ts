/**
 * HSEC document compliance campaign API client.
 */
import type { AxiosInstance } from 'axios'

export type CampaignAudienceType =
  | 'all_users'
  | 'department'
  | 'role'
  | 'group'
  | 'specific_users'

export interface CampaignGroup {
  id: number
  name: string
  member_user_ids?: number[]
  member_count?: number
  created_at?: string
}

export interface DocumentCampaign {
  id: number
  document_id: number
  status: string
  due_within_days: number
  require_quiz: boolean
  require_sign: boolean
  reminder_hours: number[]
  audience_type: CampaignAudienceType
  audience_department?: string | null
  audience_role?: string | null
  audience_group_id?: number | null
  audience_user_ids?: number[]
  assigned_count?: number
  created_at?: string
  launched_at?: string | null
}

export interface CreateCampaignPayload {
  document_id: number
  due_within_days: number
  require_quiz: boolean
  require_sign: boolean
  reminder_hours: number[]
  audience_type: CampaignAudienceType
  audience_department?: string | null
  audience_role?: string | null
  audience_group_id?: number | null
  audience_user_ids?: number[]
}

export interface LaunchCampaignResponse {
  id: number
  status: string
  assigned_count?: number
  launched_at?: string
}

export function createDocumentCampaignApi(api: AxiosInstance) {
  const base = '/api/v1/document-campaigns'

  return {
    listGroups: () => api.get<CampaignGroup[]>(`${base}/groups`),

    createGroup: (name: string, member_user_ids: number[]) =>
      api.post<CampaignGroup>(`${base}/groups`, { name, member_user_ids }),

    listCampaigns: (documentId: number) =>
      api.get<DocumentCampaign[]>(`${base}/documents/${documentId}/campaigns`),

    createCampaign: (payload: CreateCampaignPayload) =>
      api.post<DocumentCampaign>(`${base}/campaigns`, payload),

    launchCampaign: (campaignId: number) =>
      api.post<LaunchCampaignResponse>(`${base}/campaigns/${campaignId}/launch`),
  }
}
