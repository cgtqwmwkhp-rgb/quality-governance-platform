/**
 * Governed Knowledge Bank API client — evidence mapping, quizzes, discussions, regulatory watch.
 */
import type { AxiosInstance } from 'axios'

export interface KnowledgeEvidenceLink {
  id: number
  entity_type: string
  entity_id: string
  clause_id: string
  linked_by: string
  confidence: number | null
  status: string
  scheme: string | null
  auto_applied: boolean
  rationale: string | null
  title: string | null
  notes: string | null
  signal_type?: string | null
  created_at: string
  created_by_email: string | null
}

export interface RelatedDocumentHit {
  document_id: number
  score: number
  title: string | null
}

export interface AssessEntityResponse {
  entity_type: string
  entity_id: string
  signal_type: string
  links_created: number
  links: KnowledgeEvidenceLink[]
  related_documents: RelatedDocumentHit[]
  assessment_statement: string | null
  stages_summary?: Record<string, unknown> | null
}

export interface MapEvidenceResponse {
  document_id: number
  links_created: number
  links: KnowledgeEvidenceLink[]
}

export interface GenerateQuizOptions {
  question_count?: number
  include_open?: boolean
  include_mcq?: boolean
  pass_mark?: number
  auto_approve_if_quality?: boolean
}

export interface QuizDraft {
  id: number
  document_id: number
  version: string
  questions: unknown[]
  pass_mark: number
  status: string
  created_at: string
}

export interface DiscussionThread {
  id: number
  document_id: number
  version: string
  status: string
  title: string | null
  created_by_id: number
  created_at: string
}

export interface DiscussionMessage {
  id: number
  thread_id: number
  author_id: number
  body: string
  is_ai_draft: boolean
  created_at: string
}

export interface RegulatoryImpact {
  id: number
  update_id: string
  document_id: number | null
  confidence: number | null
  rationale: string | null
  status: string
  created_at: string
}

export interface ScanStandardResponse {
  standard_id: number
  links_created: number
  links: KnowledgeEvidenceLink[]
}

export function createKnowledgeBankApi(api: AxiosInstance) {
  const base = '/api/v1/knowledge-bank'

  return {
    mapEvidence: (documentId: number) =>
      api.post<MapEvidenceResponse>(`${base}/documents/${documentId}/map-evidence`),

    listDocumentEvidence: (documentId: number) =>
      api.get<KnowledgeEvidenceLink[]>(`${base}/documents/${documentId}/evidence`),

    confirmLink: (linkId: number) =>
      api.post<{ status: string; link_id: number }>(`${base}/evidence/${linkId}/confirm`),

    rejectLink: (linkId: number) =>
      api.post<{ status: string; link_id: number }>(`${base}/evidence/${linkId}/reject`),

    bulkConfirm: (ids: number[]) =>
      api.post<{ status: string; count: number }>(`${base}/evidence/bulk-confirm`, {
        link_ids: ids,
      }),

    listExceptions: (status?: string, entityType?: string) => {
      const sp = new URLSearchParams()
      if (status) sp.set('status', status)
      if (entityType) sp.set('entity_type', entityType)
      const qs = sp.toString()
      return api.get<KnowledgeEvidenceLink[]>(`${base}/exceptions${qs ? `?${qs}` : ''}`)
    },

    assessEntity: (
      entityType: string,
      entityId: string | number,
      body: {
        content?: string
        finding_type?: string
        include_related_documents?: boolean
      } = {},
    ) =>
      api.post<AssessEntityResponse>(`${base}/entities/${entityType}/${entityId}/assess`, body),

    listEntityAssessment: (entityType: string, entityId: string | number) =>
      api.get<KnowledgeEvidenceLink[]>(`${base}/entities/${entityType}/${entityId}/assessment`),

    scanStandard: (standardId: number, clauseTexts?: string[]) =>
      api.post<ScanStandardResponse>(`${base}/standards/${standardId}/scan-kb`, {
        clause_texts: clauseTexts ?? null,
      }),

    generateQuiz: (documentId: number, opts: GenerateQuizOptions = {}) =>
      api.post<QuizDraft>(`${base}/documents/${documentId}/generate-quiz`, {
        question_count: opts.question_count ?? 5,
        include_open: opts.include_open ?? true,
        include_mcq: opts.include_mcq ?? true,
        pass_mark: opts.pass_mark ?? 70,
        auto_approve_if_quality: opts.auto_approve_if_quality ?? false,
      }),

    approveQuiz: (documentId: number, draftId?: number) => {
      const sp = new URLSearchParams()
      if (draftId != null) sp.set('draft_id', String(draftId))
      const qs = sp.toString()
      return api.post<{ status: string; draft_id: number }>(
        `${base}/documents/${documentId}/approve-quiz${qs ? `?${qs}` : ''}`,
      )
    },

    listThreads: (documentId: number) =>
      api.get<DiscussionThread[]>(`${base}/documents/${documentId}/discussions`),

    createThread: (documentId: number, body: { title?: string; version?: string }) =>
      api.post<DiscussionThread>(`${base}/documents/${documentId}/discussions`, body),

    postMessage: (threadId: number, body: { body: string; use_ai_draft?: boolean }) =>
      api.post<DiscussionMessage>(`${base}/discussions/${threadId}/messages`, body),

    runRegulatoryWatch: () =>
      api.post<{ status: string; message: string }>(`${base}/regulatory-watch/run`),

    listImpacts: (status?: string) => {
      const sp = new URLSearchParams()
      if (status) sp.set('status', status)
      const qs = sp.toString()
      return api.get<RegulatoryImpact[]>(`${base}/regulatory-watch/impacts${qs ? `?${qs}` : ''}`)
    },
  }
}
