/** Closed-loop helpers: case Standards ↔ Knowledge Exceptions. */

const CASE_ENTITY_PATHS: Record<string, (id: string) => string> = {
  document: (id) => `/documents/${id}?tab=evidence`,
  incident: (id) => `/incidents/${id}`,
  complaint: (id) => `/complaints/${id}`,
  near_miss: (id) => `/near-misses/${id}`,
  rta: (id) => `/rtas/${id}`,
  audit_finding: (id) => `/audits?view=findings&findingId=${encodeURIComponent(id)}`,
}

/** Deep-link helpers — prefer detail routes; documents open Standards & Evidence tab. */
export function exceptionEntityHref(entityType: string, entityId: string): string | null {
  if (!entityId) return null
  const builder = CASE_ENTITY_PATHS[entityType]
  return builder ? builder(entityId) : null
}

/** Prevent open redirects — only same-app absolute paths. */
export function isSafeReturnTo(path: string | null | undefined): path is string {
  if (!path) return false
  if (!path.startsWith('/')) return false
  if (path.startsWith('//')) return false
  if (path.includes('://')) return false
  return true
}

const ENTITY_TYPE_VALUES = [
  'all',
  'document',
  'incident',
  'complaint',
  'near_miss',
  'rta',
  'audit_finding',
] as const

export type ExceptionsEntityTypeFilter = (typeof ENTITY_TYPE_VALUES)[number]

export function parseEntityTypeFilter(raw: string | null): ExceptionsEntityTypeFilter {
  if (raw && (ENTITY_TYPE_VALUES as readonly string[]).includes(raw)) {
    return raw as ExceptionsEntityTypeFilter
  }
  return 'all'
}

/**
 * Standards tab → Exceptions inbox deep link with entity_type filter + returnTo case.
 */
export function knowledgeExceptionsClosedLoopHref(
  entityType: string,
  entityId: number | string,
): string {
  const returnTo = exceptionEntityHref(entityType, String(entityId)) ?? '/'
  const sp = new URLSearchParams()
  sp.set('entity_type', entityType)
  sp.set('returnTo', returnTo)
  return `/knowledge-exceptions?${sp.toString()}`
}
