/**
 * Job cell link helpers (JL-3).
 *
 * Hrefs are server-resolved via X-1 href_registry — FE must never invent
 * parallel SPA URL builders for app / audit_outcome kinds.
 */
import type { JobCellLink, JobCellLinkKind } from '../../api/jobLifecycleClient'

export const JOB_CELL_LINK_KINDS: readonly JobCellLinkKind[] = [
  'app',
  'external',
  'audit_outcome',
  'job_cycle',
] as const

/** Default entity types if the registry GET is unavailable (403 / flag closed). */
export const FALLBACK_APP_ENTITY_TYPES: readonly string[] = [
  'action',
  'capa',
  'complaint',
  'document',
  'evidence_link',
  'incident',
  'job_step',
  'near_miss',
  'risk',
  'rta',
] as const

/** Registry types, minus `job_type` — nesting is the `job_cycle` kind. */
export function normaliseAppEntityTypes(items: readonly string[] | null | undefined): string[] {
  if (!items || items.length === 0) return FALLBACK_APP_ENTITY_TYPES.slice()
  const cleaned = items
    .map((item) => String(item ?? '').trim().toLowerCase())
    .filter((item) => item.length > 0 && item !== 'job_type')
  if (cleaned.length === 0) return FALLBACK_APP_ENTITY_TYPES.slice()
  return Array.from(new Set(cleaned)).sort()
}

export function shouldShowJobCellLinks(
  jobLifecycleEnabled: boolean,
  jobCellLinksEnabled: boolean,
): boolean {
  return Boolean(jobLifecycleEnabled && jobCellLinksEnabled)
}

export function jobCellLinkKindLabel(kind: JobCellLinkKind): string {
  if (kind === 'app') return 'App'
  if (kind === 'external') return 'External'
  if (kind === 'job_cycle') return 'Nested cycle'
  return 'Audit'
}

export function isJobCycleNestLink(link: Pick<JobCellLink, 'kind'>): boolean {
  return link.kind === 'job_cycle'
}

export function isExternalJobCellLink(link: Pick<JobCellLink, 'kind'>): boolean {
  return link.kind === 'external'
}

export function jobCellLinkOpenTarget(link: Pick<JobCellLink, 'kind'>): '_blank' | undefined {
  return isExternalJobCellLink(link) ? '_blank' : undefined
}

export function jobCellLinkRel(link: Pick<JobCellLink, 'kind'>): string | undefined {
  return isExternalJobCellLink(link) ? 'noopener noreferrer' : undefined
}

/** Prefer API href; never rebuild SPA paths on the client for app/audit kinds. */
export function resolveJobCellLinkHref(link: Pick<JobCellLink, 'href' | 'kind' | 'external_url'>): string {
  if (link.href && link.href.trim()) return link.href.trim()
  if (link.kind === 'external' && link.external_url) return link.external_url.trim()
  return '#'
}

export function groupJobCellLinksByKind(links: JobCellLink[]): Record<JobCellLinkKind, JobCellLink[]> {
  const grouped: Record<JobCellLinkKind, JobCellLink[]> = {
    app: [],
    external: [],
    audit_outcome: [],
    job_cycle: [],
  }
  for (const link of links) {
    if (link.kind in grouped) grouped[link.kind].push(link)
  }
  return grouped
}
