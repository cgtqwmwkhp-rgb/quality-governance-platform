/**
 * Closure-validation client shared by the four case registers.
 *
 * The API is the source of truth for whether a case may close; this client
 * exists so the Close summary dialog can show the same answer before the
 * operator commits to it.
 */
import type { AxiosInstance } from 'axios'

export type CaseClosureCaseType = 'incident' | 'complaint' | 'near_miss' | 'rta'

/** Reason codes returned by the closure gates (see docs/api/error-catalog.md). */
export const CLOSURE_REASON_MISSING_LESSONS = 'MISSING_LESSONS_LEARNT'
export const CLOSURE_REASON_OPEN_ACTIONS = 'OPEN_ACTIONS_REMAIN'

/** Reverse edge each register allows out of closed. */
export const CASE_REOPEN_STATUS: Record<CaseClosureCaseType, string> = {
  incident: 'pending_review',
  complaint: 'under_investigation',
  near_miss: 'UNDER_REVIEW',
  rta: 'under_investigation',
}

/** Status each register treats as closed. Near misses store status uppercase. */
export const CASE_CLOSED_STATUS: Record<CaseClosureCaseType, string> = {
  incident: 'closed',
  complaint: 'closed',
  near_miss: 'CLOSED',
  rta: 'closed',
}

const CASE_PATHS: Record<CaseClosureCaseType, string> = {
  incident: 'incidents',
  complaint: 'complaints',
  near_miss: 'near-misses',
  rta: 'rtas',
}

export interface CaseClosureBlockingItem {
  kind: string
  id: number
  reference_number: string
  title: string
  status: string
  action_key: string
  unblock_hint?: string
}

export interface CaseClosureLinkedInvestigation {
  id: number
  reference_number?: string | null
  title?: string | null
  status?: string | null
}

export interface CaseClosureSummary {
  case_type: string
  case_label: string
  id: number
  reference_number?: string | null
  title?: string | null
  status: string
  target_status: string
  severity?: string | null
  category?: string | null
  occurred_at?: string | null
  reported_at?: string | null
  created_at?: string | null
  closed_at?: string | null
  lessons_learnt?: string | null
  lessons_present: boolean
  actions_total: number
  actions_complete: number
  actions_incomplete: number
  linked_investigation?: CaseClosureLinkedInvestigation | null
}

export interface CaseClosureValidation {
  can_close: boolean
  reasons: string[]
  open_work: CaseClosureBlockingItem[]
  open_work_count: number
  lessons_present: boolean
  summary: CaseClosureSummary
}

/** True when `status` is the closed state for this register (case-insensitively). */
export function isCaseClosed(caseType: CaseClosureCaseType, status?: string | null): boolean {
  return (status || '').toLowerCase() === CASE_CLOSED_STATUS[caseType].toLowerCase()
}

export function createCaseClosureApi(api: AxiosInstance) {
  return {
    getValidation: (caseType: CaseClosureCaseType, caseId: number) =>
      api.get<CaseClosureValidation>(
        `/api/v1/${CASE_PATHS[caseType]}/${caseId}/closure-validation`,
      ),
  }
}
