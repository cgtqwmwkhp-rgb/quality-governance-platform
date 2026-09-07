/**
 * Assessment bind client — `/api/v1/workforce/competence/assessment-binds`
 * (CB-PR4 API, CB-UI-2 caller).
 *
 * Separate from `competenceBoardClient` on purpose. That client is read-only by
 * construction because the board must never gain a PAMS write; this one writes,
 * and everything it writes lands in QGP's own `competence_assessment_binds`
 * table. Neither client can reach PAMS: no such endpoint exists server-side.
 *
 * The endpoints 404 while `COMPETENCE_BOARD_ENABLED` is false, which is the
 * same honest answer the board gives and must be rendered as "not enabled",
 * never as "nothing is mapped".
 */
import type { AxiosInstance } from 'axios'

/** How a characteristic is demonstrated. Mirrors `BindMode` on the server. */
export type CompetenceBindMode = 'field' | 'induction'

export const COMPETENCE_BIND_MODES: CompetenceBindMode[] = ['field', 'induction']

export type CompetenceAssessmentBind = {
  id: number
  template_id: number
  characteristic_key: string
  mode: CompetenceBindMode
  /**
   * Null means this bind declares no interval, so a pass expires on the
   * competency-requirement fallback. It does **not** mean "never expires" and
   * must not be rendered as one.
   */
  interval_days?: number | null
  created_at: string
}

/** A PAMS characteristic in the current snapshot — bound or not. */
export type CompetenceCharacteristic = {
  key: string
  label: string
}

export type CompetenceBindListResponse = {
  items: CompetenceAssessmentBind[]
  /** Every characteristic the snapshot holds, including unbound ones. */
  characteristics: CompetenceCharacteristic[]
  /** Honest empty/stale notice from the server. Never a substitute for data. */
  banner?: string | null
}

export type CompetenceBindCreate = {
  template_id: number
  characteristic_key: string
  mode: CompetenceBindMode
  interval_days?: number | null
}

const BASE = '/api/v1/workforce/competence/assessment-binds'

export function createCompetenceBindApi(api: AxiosInstance) {
  return {
    list: () => api.get<CompetenceBindListResponse>(BASE),
    create: (payload: CompetenceBindCreate) => api.post<CompetenceAssessmentBind>(BASE, payload),
    remove: (bindId: number) => api.delete<void>(`${BASE}/${bindId}`),
  }
}
