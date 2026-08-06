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

export type CapaLinkOptions = {
  /** Open New Action modal with parent locked (investigation CAPA stitch). */
  create?: boolean
  /** Safe in-app return path after create (e.g. /investigations/7). */
  returnTo?: string
}

export type CapaSourceType =
  | 'incident'
  | 'investigation'
  | 'near_miss'
  | 'rta'
  | 'complaint'

export function getCapaLink(
  sourceType: CapaSourceType,
  sourceId: number,
  options?: CapaLinkOptions,
) {
  const params = new URLSearchParams({
    sourceType,
    sourceId: String(sourceId),
  })
  if (options?.create) {
    params.set('create', '1')
  }
  if (options?.returnTo && options.returnTo.startsWith('/') && !options.returnTo.startsWith('//')) {
    params.set('returnTo', options.returnTo)
  }

  return `/actions?${params.toString()}`
}

export type CapaHandoffMode = 'create' | 'open'

/** Resolve whether the CAPA hand-off CTA should invite creation or navigation. */
export function resolveCapaHandoffMode(actionsCount: number): CapaHandoffMode {
  return actionsCount > 0 ? 'open' : 'create'
}

/** Shared i18n keys for incident/investigation CAPA hand-off buttons. */
export function getCapaHandoffLabelKey(
  sourceType: CapaSourceType,
  actionsCount: number,
): string {
  if (resolveCapaHandoffMode(actionsCount) === 'open') {
    if (sourceType === 'incident') return 'incidents.detail.open_capa'
    if (sourceType === 'near_miss') return 'near_misses.detail.open_capa'
    if (sourceType === 'rta') return 'rtas.detail.open_capa'
    if (sourceType === 'complaint') return 'complaints.detail.open_capa'
    return 'investigations.handoff.open_capa'
  }
  return 'investigations.handoff.create_action'
}

export type ActionSourceLink = {
  href: string
  labelKey: string
  /** English fallback used when i18n key is missing in tests / partial locales. */
  labelFallback: string
}

/** `compliance_requirement:42` — how a compliance CAPA carries its obligation id. */
const COMPLIANCE_REQUIREMENT_REF = /^compliance_requirement:(\d+)$/i

/**
 * The obligation id behind a compliance CAPA, or null when it is not there.
 *
 * Compliance actions are the one source whose `source_id` is not the thing to
 * open: it is the occurrence (the record), because that is what distinguishes
 * one failure from the next, while the page worth landing on is the obligation.
 * The obligation id therefore rides in `source_reference`, and an action written
 * before that convention existed — or by anything that skipped it — has to
 * resolve to no link at all rather than to `/compliance-schedule/{record id}`,
 * which is a real route that would open somebody else's obligation.
 */
export function parseComplianceRequirementId(
  sourceReference: string | null | undefined,
): number | null {
  const match = COMPLIANCE_REQUIREMENT_REF.exec((sourceReference || '').trim())
  if (!match) return null
  const id = Number(match[1])
  return Number.isFinite(id) && id > 0 ? id : null
}

/**
 * Honest reverse deep-link from a unified action (incl. capa_actions) back to its source.
 * Returns null when source_id is missing/non-positive or the type has no known detail route.
 */
export function getActionSourceLink(
  sourceType: string | null | undefined,
  sourceId: number | null | undefined,
  sourceReference?: string | null,
): ActionSourceLink | null {
  if (sourceId == null || !Number.isFinite(sourceId) || sourceId <= 0) return null
  const kind = (sourceType || '').trim().toLowerCase()

  if (kind === 'compliance_record') {
    const requirementId = parseComplianceRequirementId(sourceReference)
    if (requirementId == null) return null
    return {
      href: `/compliance-schedule/${requirementId}`,
      labelKey: 'actions.view_compliance_requirement',
      labelFallback: 'View obligation',
    }
  }
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
  if (kind === 'near_miss') {
    return {
      href: `/near-misses/${sourceId}`,
      labelKey: 'actions.view_near_miss',
      labelFallback: 'View near miss',
    }
  }
  if (kind === 'rta') {
    return {
      href: `/rtas/${sourceId}`,
      labelKey: 'actions.view_rta',
      labelFallback: 'View RTA',
    }
  }
  if (kind === 'complaint' || kind === 'capa_complaint') {
    return {
      href: `/complaints/${sourceId}`,
      labelKey: 'actions.view_complaint',
      labelFallback: 'View complaint',
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
