/**
 * MAP-W3 — Stale standards-link detection + re-score / Assist audit-trail honesty.
 *
 * Pure helper for dynamic re-score when library version or question text changes.
 * Builders (MAP-W2 surfaces) can adopt later without faux auto-accept chips.
 */

export const MAP_W3_LINK_STATUSES = [
  'suggested',
  'accepted',
  'rejected',
  'stale',
] as const

export type MapW3LinkStatus = (typeof MAP_W3_LINK_STATUSES)[number]

export const MAP_W3_TRAIL_ACTIONS = [
  'assist_suggest',
  'link_accepted',
  'link_rejected',
  'marked_stale',
  'assist_rerun',
] as const

export type MapW3TrailAction = (typeof MAP_W3_TRAIL_ACTIONS)[number]

export type MapW3StaleReason = 'question_text_changed' | 'library_version_changed' | 'both'

export interface MapW3StandardLink {
  id: string
  questionId: string
  scheme: string
  refId: string
  label: string
  confidence: number
  status: MapW3LinkStatus
  /** Fingerprint captured when the link was last scored / accepted. */
  sourceFingerprint: string
  libraryVersion: string
}

export interface MapW3QuestionSnapshot {
  questionId: string
  questionText: string
  description?: string | null
}

export interface MapW3AssistTrailEntry {
  action: MapW3TrailAction
  questionId: string
  linkId?: string
  scheme?: string
  reason?: MapW3StaleReason
  fingerprint?: string
  libraryVersion?: string
  at: string
}

export interface MapW3RescoreHonesty {
  /** True when any accepted/suggested link no longer matches current text/library. */
  hasStaleLinks: boolean
  staleLinkIds: string[]
  staleReasons: Record<string, MapW3StaleReason>
  /** Author must re-run Assist — never treat stale accepted links as live. */
  needsAssistRerun: boolean
  /** Multi-scheme accept chips remain non-live until confirm loop lands. */
  assistMapLive: boolean
  acceptedMultiSchemeLinks: number
}

/** Stable, deterministic fingerprint of question text (+ optional description). */
export function fingerprintQuestionText(
  questionText: string,
  description?: string | null,
): string {
  const normalized = [questionText ?? '', description ?? '']
    .map((part) => part.trim().replace(/\s+/g, ' ').toLowerCase())
    .join('\u001f')
  let hash = 2166136261
  for (let i = 0; i < normalized.length; i += 1) {
    hash ^= normalized.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return `qfp_${(hash >>> 0).toString(16).padStart(8, '0')}`
}

export function buildSourceFingerprint(
  question: MapW3QuestionSnapshot,
  libraryVersion: string,
): string {
  const textFp = fingerprintQuestionText(question.questionText, question.description)
  const lib = (libraryVersion ?? '').trim() || 'unknown'
  return `${textFp}|lib:${lib}`
}

export function detectStaleReason(
  link: MapW3StandardLink,
  question: MapW3QuestionSnapshot,
  currentLibraryVersion: string,
): MapW3StaleReason | null {
  if (link.status === 'rejected') return null

  const currentTextFp = fingerprintQuestionText(question.questionText, question.description)
  const linkTextFp = link.sourceFingerprint.split('|')[0] ?? ''
  const textChanged = linkTextFp !== currentTextFp
  const libraryChanged =
    (link.libraryVersion ?? '').trim() !== (currentLibraryVersion ?? '').trim()

  if (textChanged && libraryChanged) return 'both'
  if (textChanged) return 'question_text_changed'
  if (libraryChanged) return 'library_version_changed'
  return null
}

/** Mark non-rejected links stale when question text or library version drifts. */
export function markStaleLinks(
  links: MapW3StandardLink[],
  questions: MapW3QuestionSnapshot[],
  currentLibraryVersion: string,
): { links: MapW3StandardLink[]; trail: MapW3AssistTrailEntry[] } {
  const byQuestion = new Map(questions.map((q) => [q.questionId, q]))
  const trail: MapW3AssistTrailEntry[] = []
  const at = new Date(0).toISOString()

  const next = links.map((link) => {
    const question = byQuestion.get(link.questionId)
    if (!question) return link
    const reason = detectStaleReason(link, question, currentLibraryVersion)
    if (!reason || link.status === 'stale') return link

    trail.push({
      action: 'marked_stale',
      questionId: link.questionId,
      linkId: link.id,
      scheme: link.scheme,
      reason,
      fingerprint: buildSourceFingerprint(question, currentLibraryVersion),
      libraryVersion: currentLibraryVersion,
      at,
    })
    return { ...link, status: 'stale' as const }
  })

  return { links: next, trail }
}

export function computeRescoreHonesty(
  links: MapW3StandardLink[],
  questions: MapW3QuestionSnapshot[],
  currentLibraryVersion: string,
): MapW3RescoreHonesty {
  const byQuestion = new Map(questions.map((q) => [q.questionId, q]))
  const staleLinkIds: string[] = []
  const staleReasons: Record<string, MapW3StaleReason> = {}

  for (const link of links) {
    if (link.status === 'rejected') continue
    const question = byQuestion.get(link.questionId)
    if (!question) continue
    const reason =
      link.status === 'stale'
        ? detectStaleReason({ ...link, status: 'accepted' }, question, currentLibraryVersion) ??
          'question_text_changed'
        : detectStaleReason(link, question, currentLibraryVersion)
    if (reason || link.status === 'stale') {
      staleLinkIds.push(link.id)
      staleReasons[link.id] = reason ?? 'question_text_changed'
    }
  }

  const acceptedLive = links.filter(
    (l) => l.status === 'accepted' && !staleLinkIds.includes(l.id),
  ).length

  return {
    hasStaleLinks: staleLinkIds.length > 0,
    staleLinkIds,
    staleReasons,
    needsAssistRerun: staleLinkIds.length > 0,
    assistMapLive: false,
    acceptedMultiSchemeLinks: acceptedLive,
  }
}

/** Append a re-run Assist audit-trail entry after author confirms re-suggest. */
export function appendAssistRerunTrail(
  trail: MapW3AssistTrailEntry[],
  questionId: string,
  libraryVersion: string,
  fingerprint: string,
  at: string = new Date(0).toISOString(),
): MapW3AssistTrailEntry[] {
  return [
    ...trail,
    {
      action: 'assist_rerun',
      questionId,
      libraryVersion,
      fingerprint,
      at,
    },
  ]
}

export function shouldPromptResuggest(honesty: MapW3RescoreHonesty): boolean {
  return honesty.needsAssistRerun && honesty.hasStaleLinks
}
