/**
 * LocationKind labels for Safety Asset / Compliance Schedule location UI.
 * Backend enum: site | workshop | premises | office (src.domain.models.location).
 */

export const LOCATION_KIND_VALUES = ['site', 'workshop', 'premises', 'office'] as const

export type LocationKindValue = (typeof LOCATION_KIND_VALUES)[number]

export const LOCATION_KIND_LABEL_KEYS: Record<
  LocationKindValue,
  { key: string; fallback: string }
> = {
  site: { key: 'admin.lookups.location_kind.site', fallback: 'Site' },
  workshop: { key: 'admin.lookups.location_kind.workshop', fallback: 'Workshop' },
  premises: { key: 'admin.lookups.location_kind.premises', fallback: 'Premises' },
  office: { key: 'admin.lookups.location_kind.office', fallback: 'Office' },
}

export function isLocationKindValue(value: string): value is LocationKindValue {
  return (LOCATION_KIND_VALUES as readonly string[]).includes(value)
}

export function locationKindLabel(
  kind: string,
  t: (key: string, fallback?: string) => string,
): string {
  if (isLocationKindValue(kind)) {
    const entry = LOCATION_KIND_LABEL_KEYS[kind]
    return t(entry.key, entry.fallback)
  }
  return kind
}
