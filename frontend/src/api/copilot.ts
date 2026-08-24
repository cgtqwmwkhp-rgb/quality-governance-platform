/**
 * PlantEx Assist API client (path: /copilot).
 *
 * Honesty rules (PX-248 / PX-250) live on the backend. This client must never
 * fabricate replies locally — callers should surface API errors (including 404
 * when the feature is disabled) rather than falling back to canned answers.
 */
import axios from 'axios'
import api from './client'

const BASE = '/api/v1/copilot'

/** Silent config so the panel can render inline unavailable/error states. */
const SILENT = { suppressErrorToast: true } as const

export interface CopilotSessionCreate {
  context_type?: string | null
  context_id?: string | null
  context_data?: Record<string, unknown> | null
  current_page?: string | null
}

export interface CopilotSession {
  id: number
  title: string | null
  context_type: string | null
  context_id: string | null
  is_active: boolean
  created_at: string
  last_message_at: string | null
}

export interface CopilotMessage {
  id: number
  session_id: number
  role: string
  content: string
  content_type: string
  action_type: string | null
  action_data: Record<string, unknown> | null
  action_result: Record<string, unknown> | null
  action_status: string | null
  created_at: string
}

export interface CopilotFeedbackCreate {
  rating: number
  feedback_type: 'helpful' | 'inaccurate' | 'inappropriate' | 'other'
  feedback_text?: string | null
}

/** True when the backend reports Copilot disabled for this environment (404). */
export function isCopilotUnavailableError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404
}

export const copilotApi = {
  createSession: (data: CopilotSessionCreate = {}) =>
    api.post<CopilotSession>(`${BASE}/sessions`, data, SILENT),

  listSessions: (params?: { offset?: number; limit?: number }) =>
    api.get<CopilotSession[]>(`${BASE}/sessions`, { params, ...SILENT }),

  getActiveSession: () =>
    api.get<CopilotSession | null>(`${BASE}/sessions/active`, SILENT),

  getSession: (sessionId: number) =>
    api.get<CopilotSession>(`${BASE}/sessions/${sessionId}`, SILENT),

  closeSession: (sessionId: number) =>
    api.delete<{ status: string }>(`${BASE}/sessions/${sessionId}`, SILENT),

  sendMessage: (sessionId: number, content: string) =>
    api.post<CopilotMessage>(
      `${BASE}/sessions/${sessionId}/messages`,
      { content },
      SILENT,
    ),

  getMessages: (sessionId: number, params?: { limit?: number }) =>
    api.get<CopilotMessage[]>(`${BASE}/sessions/${sessionId}/messages`, {
      params,
      ...SILENT,
    }),

  submitFeedback: (messageId: number, data: CopilotFeedbackCreate) =>
    api.post<{ status: string; feedback_id: number }>(
      `${BASE}/messages/${messageId}/feedback`,
      data,
      SILENT,
    ),
}
