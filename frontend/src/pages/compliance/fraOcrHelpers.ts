/**
 * Pure helpers for FRA / PAS79 OCR ingest UI.
 */
import type { ComplianceRequirement } from '../../api/complianceScheduleClient'
import type {
  FraFieldConfidence,
  FraOcrDraftResponse,
} from '../../api/complianceScheduleFraOcrClient'

/** Catalogue / Library taxonomy for Fire Risk Assessment. */
export const FRA_TAXONOMY_ID = '03.01'

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/**
 * Site-scoped active FRA obligations only. Org-wide or non-FRA rows cannot
 * accept an FRA OCR draft (backend rejects them too).
 */
export function isFraOcrEligible(
  requirement: Pick<ComplianceRequirement, 'is_active' | 'location_id' | 'taxonomy_id'>,
): boolean {
  return (
    requirement.is_active === true &&
    requirement.location_id != null &&
    requirement.taxonomy_id === FRA_TAXONOMY_ID
  )
}

/**
 * Prefill for the human-gate due date from the proposed next review date.
 * Returns '' when the proposal is missing or not an ISO calendar date — the
 * operator must still type a value; we never invent one.
 */
export function proposeNextDueDate(draft: FraOcrDraftResponse): string {
  const raw = draft.proposed?.next_review_date?.value
  if (typeof raw !== 'string') return ''
  const trimmed = raw.trim()
  return ISO_DATE_RE.test(trimmed) ? trimmed : ''
}

export function confidenceChipClass(confidence: FraFieldConfidence | null | undefined): string {
  switch (confidence) {
    case 'high':
      return 'bg-emerald-500/10 text-emerald-700'
    case 'medium':
      return 'bg-amber-500/10 text-amber-800'
    case 'none':
    default:
      return 'bg-muted text-muted-foreground'
  }
}
