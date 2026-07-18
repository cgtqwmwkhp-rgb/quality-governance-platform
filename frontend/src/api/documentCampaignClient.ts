/**
 * Document compliance campaign API client (HSEC launch + engineer My Reading).
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
  audience_type?: CampaignAudienceType
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
  campaign_id?: number
  notified_count?: number
}

export interface DocumentCampaignAssignment {
  id: number
  campaign_id?: number
  campaign_title?: string | null
  document_id: number
  document_title?: string | null
  document_version?: string | null
  status: string
  assigned_at?: string | null
  due_date?: string | null
  due_at?: string | null
  opened_at?: string | null
  first_opened_at?: string | null
  completed_at?: string | null
  quiz_required?: boolean
  requires_quiz?: boolean
  require_quiz?: boolean
  quiz_score?: number | null
  quiz_passed?: boolean | null
}

export interface DocumentCampaignAssignmentListResponse {
  items: DocumentCampaignAssignment[]
  total: number
}

export interface DocumentCampaignQuizQuestion {
  question_index?: number
  question?: string
  question_text?: string
  type?: 'mcq' | 'multiple_choice' | 'open_text' | 'text'
  question_type?: 'mcq' | 'multiple_choice' | 'open_text' | 'text'
  options?: string[]
}

export interface DocumentCampaignQuiz {
  questions: DocumentCampaignQuizQuestion[]
  pass_mark?: number | null
}

export interface DocumentCampaignQuizAnswer {
  question_index: number
  selected_option?: string
  text_answer?: string
}

export interface DocumentCampaignQuizResult {
  score?: number | null
  passed?: boolean | null
  quiz_score?: number | null
  quiz_passed?: boolean | null
  pass_mark?: number | null
}

export interface CompleteDocumentCampaignAssignmentRequest {
  acceptance_statement: string
  signature_data?: string
}

export function createDocumentCampaignApi(api: AxiosInstance) {
  const base = '/api/v1/document-campaigns'

  return {
    // HSEC launch (#1146)
    listGroups: () => api.get<CampaignGroup[]>(`${base}/groups`),
    createGroup: (name: string, member_user_ids: number[]) =>
      api.post<CampaignGroup>(`${base}/groups`, { name, member_user_ids }),
    listCampaigns: (documentId: number) =>
      api.get<DocumentCampaign[]>(`${base}/documents/${documentId}/campaigns`),
    createCampaign: (payload: CreateCampaignPayload) =>
      api.post<DocumentCampaign>(`${base}/campaigns`, payload),
    launchCampaign: (campaignId: number) =>
      api.post<LaunchCampaignResponse>(`${base}/campaigns/${campaignId}/launch`),

    // Engineer My Reading (#1147)
    listMyAssignments: () =>
      api.get<DocumentCampaignAssignmentListResponse>(`${base}/my-assignments`),
    openAssignment: (assignmentId: number) =>
      api.post<DocumentCampaignAssignment>(`${base}/assignments/${assignmentId}/open`),
    getAssignmentQuiz: (assignmentId: number) =>
      api.get<DocumentCampaignQuiz>(`${base}/assignments/${assignmentId}/quiz`),
    submitQuiz: (assignmentId: number, answers: DocumentCampaignQuizAnswer[]) =>
      api.post<DocumentCampaignQuizResult>(`${base}/assignments/${assignmentId}/quiz`, {
        answers,
      }),
    completeAssignment: (
      assignmentId: number,
      data: CompleteDocumentCampaignAssignmentRequest,
    ) =>
      api.post<DocumentCampaignAssignment>(`${base}/assignments/${assignmentId}/complete`, data),
  }
}
