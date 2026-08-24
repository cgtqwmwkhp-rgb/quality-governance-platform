/**
 * L-36 — project a Register row onto the Front Sheet band.
 *
 * Pure: no fetching, no defaults invented for a field the API did not send. A
 * missing value becomes `null` and the band renders it as missing, because a
 * cover sheet that fills its own gaps is worse than one with holes in it.
 */
import { documentRegisterPrimaryRef } from '../pages/documentsRegisterHelpers'
import { describeLibraryRetention } from './retentionDisplay'
import type { FrontSheetBandModel, LibraryBodyDocument } from './types'

function trimmedOrNull(raw: string | null | undefined): string | null {
  const value = (raw ?? '').trim()
  return value ? value : null
}

/**
 * `PEL-<CODE>-<BAND><SEQ>` (R01) — the function is everything between the `PEL`
 * prefix and the final segment, so a hyphenated function code survives. Falls
 * back to the department only when no PEL reference is allocated; it is never
 * derived from the band digit.
 */
export function libraryFunctionCode(
  pelDocRef: string | null | undefined,
  department?: string | null,
): string | null {
  const ref = (pelDocRef ?? '').trim().toUpperCase()
  if (ref.startsWith('PEL-')) {
    const prefix = ref.slice(0, ref.lastIndexOf('-'))
    const code = prefix.slice('PEL-'.length).trim()
    if (code) return code
  }
  return trimmedOrNull(department)
}

export function buildFrontSheetBandModel(document: LibraryBodyDocument): FrontSheetBandModel {
  const primary = documentRegisterPrimaryRef({
    reference_number: document.reference_number ?? null,
    pel_doc_ref: document.pel_doc_ref ?? null,
  })
  const version = trimmedOrNull(document.version)

  return {
    documentId: document.id,
    title: (document.title ?? '').trim(),
    leadReference: primary.lead,
    secondaryReference: primary.secondary,
    issueLabel: version ? `v${version}` : null,
    statusLabel: trimmedOrNull(document.status),
    controlStatusLabel: trimmedOrNull(document.control_status),
    functionCode: libraryFunctionCode(document.pel_doc_ref, document.department),
    cascadeLevel:
      typeof document.cascade_level === 'number' && Number.isFinite(document.cascade_level)
        ? document.cascade_level
        : null,
    accessLevel: trimmedOrNull(document.access_level),
    isStatutory: Boolean(document.is_statutory),
    legalHoldActive: Boolean(document.legal_hold_active),
    legalMatterReference: trimmedOrNull(document.legal_matter_reference),
    fileName: trimmedOrNull(document.file_name),
    effectiveDate: trimmedOrNull(document.effective_date),
    reviewDate: trimmedOrNull(document.review_date),
    retention: describeLibraryRetention(document),
    // CEL / evidence-pack composition is not built, so there is nothing honest
    // to summarise here yet. Null renders as "not composed", not as "none".
    coverageSummary: null,
  }
}
