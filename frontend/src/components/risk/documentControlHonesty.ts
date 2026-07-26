/**
 * PX-263: Document Control empty-state honesty.
 *
 * Distinguishes a filter miss from an unpopulated controlled register, and
 * acknowledges that the Library may still hold uncontrolled policy uploads
 * (ISO 9001 / 45001 clause 7.5 gap) without claiming those are controlled.
 */

export type DocumentControlEmptyKind = 'filtered' | 'unpopulated'

export type DocumentControlEmptyCopy = {
  kind: DocumentControlEmptyKind
  title: string
  description: string
}

export function buildDocumentControlEmptyCopy(opts: {
  hasActiveFilters: boolean
  libraryDocumentCount: number | null
}): DocumentControlEmptyCopy {
  if (opts.hasActiveFilters) {
    return {
      kind: 'filtered',
      title: 'No controlled documents match these filters',
      description:
        'Clear search or status filters to see the full controlled register. A filtered empty view is not the same as an unpopulated Document Control module.',
    }
  }

  const libraryBit =
    typeof opts.libraryDocumentCount === 'number' && opts.libraryDocumentCount > 0
      ? ` The Library currently holds ${opts.libraryDocumentCount} document${
          opts.libraryDocumentCount === 1 ? '' : 's'
        } that are not on this controlled lifecycle.`
      : ' Policies may still circulate as plain Library uploads without version, approval, review, or retention control.'

  return {
    kind: 'unpopulated',
    title: 'No controlled documents',
    description:
      'Nothing has entered the controlled document workflow yet — this is an ISO 9001 / ISO 45001 clause 7.5 gap, not a filter result.' +
      libraryBit +
      ' Create a draft shell here, or open the Library to locate existing uploads.',
  }
}
