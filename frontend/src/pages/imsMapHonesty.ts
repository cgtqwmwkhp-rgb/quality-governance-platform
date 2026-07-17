/** Multi-scheme standards map honesty helpers (MAP-W1). */

export const MAP_W1_SCHEME_CHIPS = ['ISO', 'Planet Mark', 'UVDB'] as const

export type MapW1SchemeChip = (typeof MAP_W1_SCHEME_CHIPS)[number]

export interface CrossStandardMappingLike {
  primary_standard?: string | null
  mapped_standard?: string | null
}

/** Infer which assurance schemes appear in live cross-standard mapping rows. */
export function detectSchemesInMappings(
  mappings: CrossStandardMappingLike[],
): MapW1SchemeChip[] {
  const haystack = mappings
    .flatMap((m) => [m.primary_standard ?? '', m.mapped_standard ?? ''])
    .join(' ')
    .toLowerCase()

  const present: MapW1SchemeChip[] = []
  if (/(iso|annex\s*sl|9001|14001|45001|27001)/i.test(haystack)) present.push('ISO')
  if (/planet\s*mark|carbon/i.test(haystack)) present.push('Planet Mark')
  if (/uvdb|achilles/i.test(haystack)) present.push('UVDB')
  return present
}

/** Management-review rows that claim Planet Mark / UVDB without a live feed. */
export function isDemoSchemeReviewSource(source: string): boolean {
  const value = source.trim().toLowerCase()
  return value.includes('planet mark') || value.includes('uvdb')
}
