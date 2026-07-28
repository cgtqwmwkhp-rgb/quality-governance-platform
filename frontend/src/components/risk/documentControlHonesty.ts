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

/**
 * Parts of a document-detail payload the server could not read.
 *
 * The server sends `distributions: []` alongside this block, because this page
 * reads `detail.distributions.length` and a missing key would crash it. That
 * makes an empty array indistinguishable from "no controlled copies were issued"
 * on its own — so whenever this block is present, the empty array must not be
 * rendered as an empty state. That is the entire reason the type exists.
 */
export type DocumentDetailUnavailable = {
  fields: string[]
  missing_tables: string[]
  provisioning_state?: string
  reasons?: Record<string, string>
}

export type DocumentControlUnavailableCopy = {
  show: boolean
  title: string
  description: string
}

const NEVER_BUILT_SUFFIX =
  ' This part of Document Control has no database table in this deployment, so it is not a fault that will clear on retry — it needs a migration to be deployed.'

/**
 * Copy for a distribution list that was never read.
 *
 * Deliberately does not say "no controlled copies" or "none yet". The whole
 * defect being fixed is that an unread list and an empty list produced the same
 * sentence.
 */
export function buildDistributionsUnavailableCopy(
  unavailable: DocumentDistributionsUnavailableInput,
): DocumentControlUnavailableCopy {
  if (!unavailable?.fields?.includes('distributions')) {
    return { show: false, title: '', description: '' }
  }

  const tables = unavailable.missing_tables ?? []
  const tableBit = tables.length > 0 ? ` Missing table${tables.length === 1 ? '' : 's'}: ${tables.join(', ')}.` : ''

  return {
    show: true,
    title: 'Controlled-copy distribution list unavailable',
    description:
      'This document may or may not have controlled copies issued — the record could not be read, so nothing here should be taken as evidence either way.' +
      tableBit +
      NEVER_BUILT_SUFFIX,
  }
}

/** Copy for a view that was not written to the access log. */
export function buildAccessLogUnavailableCopy(
  unavailable: DocumentDistributionsUnavailableInput,
): DocumentControlUnavailableCopy {
  if (!unavailable?.fields?.includes('access_log')) {
    return { show: false, title: '', description: '' }
  }

  return {
    show: true,
    title: 'Document access is not being logged',
    description:
      'Opening this document was not recorded, and its access history cannot be read. Do not rely on this document having an audit trail of who viewed it.' +
      NEVER_BUILT_SUFFIX,
  }
}

type DocumentDistributionsUnavailableInput = DocumentDetailUnavailable | null | undefined
