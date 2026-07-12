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
