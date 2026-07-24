import type { AxiosInstance } from 'axios'

export interface AuditChallengeCitation {
  scheme: string
  refId: string
  label: string
  url?: string | null
}

export interface AuditChallengeChip {
  id: string
  label: string
  prompt: string
}

export interface AuditChallengeTurn {
  id: number
  role: 'user' | 'critic' | 'author' | 'system'
  content: string
  chip_id?: string | null
  citations: AuditChallengeCitation[]
  sort_order: number
  created_at?: string | null
}

export interface AuditChallengeProposal {
  id: number
  proposal_key: string
  target_path: string
  change_type: string
  dimension?: string | null
  assessor_failure_mode?: string | null
  before?: Record<string, unknown> | null
  after?: Record<string, unknown> | null
  rationale?: string | null
  citations: AuditChallengeCitation[]
  decision: 'pending' | 'accepted' | 'rejected' | 'edited'
}

export interface AuditChallengeSession {
  id: number
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  progress_pct: number
  progress_message?: string | null
  chip_id?: string | null
  user_message?: string | null
  template_id?: number | null
  brief?: Record<string, unknown>
  models_used?: Record<string, unknown> | null
  grounding?: Record<string, unknown> | null
  error_code?: string | null
  error_detail?: string | null
  chips: AuditChallengeChip[]
  turns: AuditChallengeTurn[]
  proposals: AuditChallengeProposal[]
  created_at?: string | null
  completed_at?: string | null
}

export interface AuditChallengeSessionCreatePayload {
  sections: unknown[]
  brief?: Record<string, unknown>
  chip_id?: string
  message?: string
  template_id?: number
}

export interface AuditChallengeApplyResult {
  sections: unknown[]
  applied_count: number
}

const BASE = '/api/v1/ai-templates/challenge'

export function createAuditChallengeApi(api: AxiosInstance) {
  return {
    createSession: (payload: AuditChallengeSessionCreatePayload) =>
      api.post<AuditChallengeSession>(`${BASE}/sessions`, payload),
    getSession: (sessionId: number) => api.get<AuditChallengeSession>(`${BASE}/sessions/${sessionId}`),
    sendMessage: (sessionId: number, message: string, chipId?: string) =>
      api.post<AuditChallengeSession>(`${BASE}/sessions/${sessionId}/messages`, {
        message,
        chip_id: chipId,
      }),
    decideProposal: (
      sessionId: number,
      proposalId: number,
      decision: 'accept' | 'reject' | 'edit',
      editedAfter?: Record<string, unknown>,
    ) =>
      api.post<AuditChallengeProposal>(`${BASE}/sessions/${sessionId}/proposals/${proposalId}/decide`, {
        decision,
        edited_after: editedAfter,
      }),
    applySession: (sessionId: number) =>
      api.post<AuditChallengeApplyResult>(`${BASE}/sessions/${sessionId}/apply`),
  }
}
