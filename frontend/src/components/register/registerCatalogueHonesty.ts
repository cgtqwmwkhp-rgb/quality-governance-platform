import {
  REGISTER_ALLOWED_ROUTES,
  REGISTER_CATALOGUE,
  type RegisterBand,
  type RegisterEntry,
} from '../../data/registerCatalogue'

const LINKABLE_BANDS: ReadonlySet<RegisterBand> = new Set(['live', 'caption', 'hub'])

export const BAND_LABEL: Record<RegisterBand, string> = {
  live: 'LIVE',
  caption: 'Caption',
  document: 'Document',
  absent: 'Not captured',
  hub: 'This hub',
}

export function catalogueHasRecordCounts(entries: readonly RegisterEntry[] = REGISTER_CATALOGUE): boolean {
  return entries.some((entry) => 'recordCount' in entry || 'count' in entry)
}

const CAPTION_QUERY_KEYS = new Set(['register', 'type', 'statutory'])
const INCIDENT_TYPE_VALUES = new Set([
  'injury',
  'near_miss',
  'hazard',
  'property_damage',
  'environmental',
  'security',
  'quality',
  'other',
])

export function registerHref(entry: RegisterEntry): string {
  if (!entry.to) return ''
  return entry.captionQuery ? `${entry.to}?${entry.captionQuery}` : entry.to
}

export function lookupRegister(docRef: string | null): RegisterEntry | undefined {
  if (!docRef) return undefined
  return REGISTER_CATALOGUE.find((entry) => entry.docRef === docRef)
}

export function isLinkableRegister(entry: RegisterEntry): boolean {
  return LINKABLE_BANDS.has(entry.band) && Boolean(entry.to)
}

export type HubOpenKind = 'link' | 'schedule-off' | 'none'

/**
 * Hub Open column. Schedule tiles must not look like a working list when
 * `compliance_schedule` is off — the router 404s and "coming soon" would lie.
 */
export function hubOpenKind(
  entry: RegisterEntry,
  flags: { compliance_schedule: boolean },
): HubOpenKind {
  if (!isLinkableRegister(entry) || !entry.to) return 'none'
  if (entry.to === '/compliance-schedule' && !flags.compliance_schedule) {
    return 'schedule-off'
  }
  return 'link'
}

export function assertRegisterCatalogueIntegrity(
  entries: readonly RegisterEntry[] = REGISTER_CATALOGUE,
): string[] {
  const errors: string[] = []
  if (entries.length !== 56) {
    errors.push(`expected 56 rows, got ${entries.length}`)
  }
  const seen = new Set<string>()
  for (const entry of entries) {
    if (seen.has(entry.docRef)) {
      errors.push(`duplicate ${entry.docRef}`)
    }
    seen.add(entry.docRef)
    if (LINKABLE_BANDS.has(entry.band)) {
      if (!entry.to) {
        errors.push(`${entry.docRef} band ${entry.band} has no to`)
      } else if (!REGISTER_ALLOWED_ROUTES.includes(entry.to)) {
        errors.push(`${entry.docRef} to ${entry.to} is not an allowed route`)
      }
    } else if (entry.to) {
      errors.push(`${entry.docRef} band ${entry.band} must not have a to`)
    }
    if (entry.captionQuery) {
      if (!entry.to) {
        errors.push(`${entry.docRef} captionQuery requires to`)
      }
      const params = new URLSearchParams(entry.captionQuery)
      const register = params.get('register')
      if (register !== entry.docRef) {
        errors.push(`${entry.docRef} captionQuery register must equal docRef`)
      }
      for (const key of params.keys()) {
        if (!CAPTION_QUERY_KEYS.has(key)) {
          errors.push(`${entry.docRef} captionQuery has forbidden key ${key}`)
        }
      }
      const type = params.get('type')
      if (type && !INCIDENT_TYPE_VALUES.has(type)) {
        errors.push(`${entry.docRef} captionQuery type ${type} is not an incident type`)
      }
      const statutory = params.get('statutory')
      if (statutory !== null && statutory !== 'true' && statutory !== 'false') {
        errors.push(`${entry.docRef} captionQuery statutory must be true or false`)
      }
    }
    if ('recordCount' in entry || 'count' in entry) {
      errors.push(`${entry.docRef} must not carry a record count`)
    }
  }
  const live = entries.filter((e) => e.band === 'live')
  if (live.length !== 9) {
    errors.push(`expected 9 live rows, got ${live.length}`)
  }
  const hub = entries.filter((e) => e.band === 'hub')
  if (hub.length !== 1 || hub[0]?.docRef !== 'PEL-HSEQ-5062') {
    errors.push('expected PEL-HSEQ-5062 as the sole hub row')
  }
  return errors
}
