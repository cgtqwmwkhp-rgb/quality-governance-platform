import type { Investigation } from '../../api/client'

type InvestigationSourceType = Investigation['assigned_entity_type']

const SOURCE_ROUTES: Partial<Record<InvestigationSourceType, string>> = {
  reporting_incident: '/incidents',
  near_miss: '/near-misses',
  road_traffic_collision: '/rtas',
}

const SOURCE_LABELS: Partial<Record<InvestigationSourceType, string>> = {
  reporting_incident: 'incident',
  near_miss: 'near miss',
  road_traffic_collision: 'RTA',
}

export function getInvestigationSourceLink(investigation: Investigation) {
  const route = SOURCE_ROUTES[investigation.assigned_entity_type]
  const label = SOURCE_LABELS[investigation.assigned_entity_type]

  if (!route || !label) return null

  return {
    href: `${route}/${investigation.assigned_entity_id}`,
    label,
  }
}

export function getCapaLink(sourceType: 'incident' | 'investigation', sourceId: number) {
  const params = new URLSearchParams({
    sourceType,
    sourceId: String(sourceId),
  })

  return `/actions?${params.toString()}`
}

export type CapaHandoffMode = 'create' | 'open'

/** Resolve whether the CAPA hand-off CTA should invite creation or navigation. */
export function resolveCapaHandoffMode(actionsCount: number): CapaHandoffMode {
  return actionsCount > 0 ? 'open' : 'create'
}

/** Shared i18n keys for incident/investigation CAPA hand-off buttons. */
export function getCapaHandoffLabelKey(
  sourceType: 'incident' | 'investigation',
  actionsCount: number,
): string {
  if (resolveCapaHandoffMode(actionsCount) === 'open') {
    return sourceType === 'incident'
      ? 'incidents.detail.open_capa'
      : 'investigations.handoff.open_capa'
  }
  return 'investigations.handoff.create_action'
}

export type ActionSourceLink = {
  href: string
  labelKey: string
  /** English fallback used when i18n key is missing in tests / partial locales. */
  labelFallback: string
}

/**
 * Honest reverse deep-link from a unified action (incl. capa_actions) back to its source.
 * Returns null when source_id is missing/non-positive or the type has no known detail route.
 */
export function getActionSourceLink(
  sourceType: string | null | undefined,
  sourceId: number | null | undefined,
): ActionSourceLink | null {
  if (sourceId == null || !Number.isFinite(sourceId) || sourceId <= 0) return null
  const kind = (sourceType || '').trim().toLowerCase()

  if (kind === 'incident' || kind === 'capa_incident') {
    return {
      href: `/incidents/${sourceId}`,
      labelKey: 'actions.view_incident',
      labelFallback: 'View incident',
    }
  }
  if (kind === 'investigation') {
    return {
      href: `/investigations/${sourceId}`,
      labelKey: 'actions.view_investigation',
      labelFallback: 'View investigation',
    }
  }
  if (kind === 'audit_finding') {
    return {
      href: `/audits?view=findings&findingId=${sourceId}`,
      labelKey: 'actions.view_finding',
      labelFallback: 'View finding',
    }
  }
  return null
}

/**
 * Residual honesty for CAPA counts: never render "0" when the load failed.
 * Loading → ellipsis; unavailable → em dash; else the live count.
 */
export function formatCapaActionsCount(options: {
  loading?: boolean
  unavailable?: boolean
  count: number
}): string {
  if (options.loading) return '…'
  if (options.unavailable) return '—'
  return String(options.count)
}

/** Deep link to an investigation detail from a near-miss (or other) source list. */
export function getInvestigationDetailHref(investigationId: number): string {
  return `/investigations/${investigationId}`
}
