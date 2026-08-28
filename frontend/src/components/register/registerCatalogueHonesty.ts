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

export function isLinkableRegister(entry: RegisterEntry): boolean {
  return LINKABLE_BANDS.has(entry.band) && Boolean(entry.to)
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
