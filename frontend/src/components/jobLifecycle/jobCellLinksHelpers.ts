/**
 * Job cell link helpers (JL-3).
 *
 * Hrefs are server-resolved via X-1 href_registry — FE must never invent
 * parallel SPA URL builders for app / audit_outcome kinds.
 */
import type { JobCellLink, JobCellLinkKind } from '../api/jobLifecycleClient'

export const JOB_CELL_LINK_KINDS: readonly JobCellLinkKind[] = [
  'app',
  'external',
  'audit_outcome',
] as const

export function shouldShowJobCellLinks(
  jobLifecycleEnabled: boolean,
  jobCellLinksEnabled: boolean,
): boolean {
  return Boolean(jobLifecycleEnabled && jobCellLinksEnabled)
}

export function jobCellLinkKindLabel(kind: JobCellLinkKind): string {
  if (kind === 'app') return 'App'
  if (kind === 'external') return 'External'
  return 'Audit'
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
  }
  for (const link of links) {
    if (link.kind in grouped) grouped[link.kind].push(link)
  }
  return grouped
}
