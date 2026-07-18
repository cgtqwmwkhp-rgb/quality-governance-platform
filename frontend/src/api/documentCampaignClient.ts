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

export type SignatureDisposition =
  | 'signed'
  | 'signature_deferred_pending_answer'
  | 'signed_pending_hseq_answer'

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
  snooze_until?: string | null
  quiz_required?: boolean
  requires_quiz?: boolean
  require_quiz?: boolean
  quiz_score?: number | null
  quiz_passed?: boolean | null
  quiz_attempts?: number
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
  quiz_attempts?: number
}

export interface CompleteDocumentCampaignAssignmentRequest {
  acceptance_statement: string
  signature_data?: string
  signature_disposition?: SignatureDisposition
}

export interface AssignmentDocumentUrlResponse {
  assignment_id: number
  document_id: number
  signed_url: string
  expires_in_seconds: number
  filename: string
  content_type?: string | null
}


export interface CompliancePassportAssignment {
  id: number
  campaign_id: number
  document_id: number
  document_title: string
  campaign_title?: string | null
  status: string
  assigned_at: string
  due_at: string
  completed_at?: string | null
  quiz_score?: number | null
  quiz_passed?: boolean | null
}

export interface CompliancePassportStats {
  completion_rate: number
  quiz_pass_rate: number
  total_assigned: number
}

export interface CompliancePassportResponse {
  outstanding: CompliancePassportAssignment[]
  completed: CompliancePassportAssignment[]
  stats: CompliancePassportStats
}

export interface ReminderDefaults {
  reminder_hours: number[]
}

export interface SnoozeAssignmentResponse {
  id: number
  snooze_until: string
  message?: string
}

export interface GroupComplianceRow {
  group_id: number | null
  group_name: string
  assigned: number
  completed: number
  pending: number
  overdue: number
  quiz_pass_count: number
  completion_rate: number
}

export interface GroupComplianceListResponse {
  campaign_id: number
  items: GroupComplianceRow[]
  total: number
}

export interface CampaignComplianceRow {
  campaign_id: number
  document_id: number
  document_title: string
  status: string
  assigned: number
  completed: number
  pending: number
  overdue: number
  completion_rate: number
  quiz_pass_count?: number
  audience_group_ids?: number[]
  reminder_offsets_hours: number[]
  launched_at: string | null
  due_within_days: number
  title?: string | null
}

export interface QuestionInboxThread {
  thread_id: number
  document_id: number
  document_title: string
  thread_title?: string | null
  title?: string | null
  status: string
  created_at: string
  created_by_id: number
  latest_message_preview?: string | null
  latest_message?: { body: string } | null
}

export interface ComplianceListResponse {
  items: CampaignComplianceRow[]
  total: number
}

export interface QuestionInboxListResponse {
  items: QuestionInboxThread[]
  total: number
}

export interface AskAssignmentQuestionPayload {
  title?: string
  body: string
}

export interface ReplyQuestionPayload {
  body: string
}

function triggerJsonDownload(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
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
    getAssignmentDocumentUrl: (assignmentId: number) =>
      api.get<AssignmentDocumentUrlResponse>(`${base}/assignments/${assignmentId}/document-url`),
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

    // EPIC-2: reminder defaults, compliance, evidence, HSEC inbox
    getReminderDefaults: () => api.get<ReminderDefaults>(`${base}/reminder-defaults`),
    setReminderDefaults: (reminder_hours: number[]) =>
      api.put<ReminderDefaults>(`${base}/reminder-defaults`, { reminder_hours }),
    listCompliance: () => api.get<ComplianceListResponse>(`${base}/compliance`),
    downloadEvidencePack: async (campaignId: number) => {
      const response = await api.get(`${base}/campaigns/${campaignId}/evidence-pack`, {
        responseType: 'json',
      })
      triggerJsonDownload(
        response.data,
        `campaign-evidence-${campaignId}-${new Date().toISOString().slice(0, 10)}.json`,
      )
      return response
    },
    listQuestionInbox: () => api.get<QuestionInboxListResponse>(`${base}/question-inbox`),
    askAssignmentQuestion: (assignmentId: number, payload: AskAssignmentQuestionPayload) =>
      api.post(`${base}/assignments/${assignmentId}/questions`, payload),
    replyQuestion: (threadId: number, payload: ReplyQuestionPayload) =>
      api.post(`${base}/questions/${threadId}/reply`, payload),
    resolveQuestion: (threadId: number) => api.post(`${base}/questions/${threadId}/resolve`),
    snoozeAssignment: (assignmentId: number, hours: number) =>
      api.post<SnoozeAssignmentResponse>(`${base}/assignments/${assignmentId}/snooze`, { hours }),
    getComplianceByGroup: (campaignId: number) =>
      api.get<GroupComplianceListResponse>(`${base}/compliance/${campaignId}/by-group`),
    getMyPassport: () => api.get<CompliancePassportResponse>(`${base}/my-passport`),

    downloadEvidencePackCsv: (campaignId: number) =>
      api.get<Blob>(`${base}/campaigns/${campaignId}/evidence-pack.csv`, {
        responseType: 'blob',
      }),

    spawnReackCampaign: (documentId: number) =>
      api.post<{ spawned: boolean; campaign_id?: number; source_campaign_id?: number; reason?: string }>(
        `/api/v1/documents/${documentId}/spawn-reack-campaign`,
      ),

  }
}
