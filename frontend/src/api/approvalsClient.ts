/**
 * Approvals read-model client: what decisions are outstanding for this user.
 *
 * Reads `GET /api/v1/approvals/my-decisions`, which aggregates the domains that
 * hold pending decisions (investigations, controlled documents, signatures). It
 * has no write half by design — a decision is recorded by the domain that raised
 * it, so this client cannot approve anything.
 */
import type { AxiosInstance } from 'axios'

/** One outstanding decision, as the owning domain reported it. */
export interface PendingDecision {
  /** `{source}:{id}` — stable within a source. A list key, not an id. */
  key: string
  source: string
  source_label: string
  /** The verb the owning domain uses: `approve`, `review`, `sign`. */
  decision: string
  title: string
  reference?: string | null
  requested_at?: string | null
  /**
   * What `requested_at` is a record of: `submitted`, `raised`, or `last_updated`
   * where the domain does not timestamp the transition. Rendered as a qualifier
   * on the date, because showing a last-updated stamp under the heading
   * "requested" is a claim the record does not support.
   */
  requested_at_basis?: 'submitted' | 'raised' | 'last_updated' | null
  due_at?: string | null
  /**
   * Route to the screen that owns the record, or null when this product has no
   * screen that reads it. Null renders as "no screen yet" — never as a guessed
   * route, which would send someone holding real work to the wrong page.
   */
  deep_link?: string | null
}

/** Whether a domain could be asked, and what it said. */
export interface DecisionSource {
  key: string
  label: string
  status: 'live' | 'unavailable' | string
  /** Null when `status` is `unavailable`. Zero only ever means zero. */
  count?: number | null
  reason?: string | null
  /** Rows naming no approver, so outstanding for nobody and in no user's queue. */
  unattributed?: number
  /** True when a per-source cap cut the list, making `count` a floor. */
  truncated?: boolean
}

export interface MyDecisionsResponse {
  items: PendingDecision[]
  total: number
  sources_complete: boolean
  unavailable_sources: string[]
  sources: DecisionSource[]
}

/**
 * Whether every source answered, so an empty list may be read as "nothing waiting".
 *
 * Absent field → **false**, the opposite of `actionsAreComplete`. That helper
 * treats absent as complete for back-compat with servers older than the field,
 * and can afford to: a partial action register still shows actions. Here the
 * whole surface is the claim "these are all your decisions", and a response we
 * cannot interpret is not evidence for it. There is also no older server to be
 * compatible with — this endpoint shipped with the field.
 */
export function decisionsAreComplete(response: { sources_complete?: boolean }): boolean {
  return response.sources_complete === true
}

/**
 * Names the sources that could not be read, using the labels the server sent.
 *
 * Deliberately not a hardcoded key→label map like the actions client's: that map
 * silently falls back to the raw key when the server adds a source, and this
 * response already carries a label per source. One less thing to keep in step.
 */
export function describeUnavailableDecisionSources(response: {
  unavailable_sources?: string[]
  sources?: DecisionSource[]
}): string {
  const keys = response.unavailable_sources ?? []
  if (keys.length === 0) return ''
  return keys
    .map((key) => response.sources?.find((source) => source.key === key)?.label ?? key)
    .join(', ')
}

/** Reasons the server gave for each unreadable source, for the detail line. */
export function unavailableSourceReasons(response: {
  unavailable_sources?: string[]
  sources?: DecisionSource[]
}): string[] {
  const keys = new Set(response.unavailable_sources ?? [])
  return (response.sources ?? [])
    .filter((source) => keys.has(source.key))
    .map((source) => source.reason)
    .filter((reason): reason is string => Boolean(reason))
}

/**
 * Pending decisions the domains hold but could not attribute to anybody.
 *
 * Surfaced rather than summed into the caller's count: these are somebody's
 * problem and nobody's queue, which is a configuration defect worth naming.
 */
export function unattributedDecisionCount(response: { sources?: DecisionSource[] }): number {
  return (response.sources ?? []).reduce((total, source) => total + (source.unattributed ?? 0), 0)
}

export function createApprovalsApi(api: AxiosInstance) {
  return {
    /** Decisions waiting on the caller, with the state of every source asked. */
    myDecisions: () => api.get<MyDecisionsResponse>('/api/v1/approvals/my-decisions'),
  }
}
