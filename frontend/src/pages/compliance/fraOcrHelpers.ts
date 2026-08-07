/**
 * Pure helpers for FRA / PAS79 OCR ingest UI.
 */
import type { ComplianceRequirement } from '../../api/complianceScheduleClient'
import type {
  FraFieldConfidence,
  FraOcrDraftResponse,
} from '../../api/complianceScheduleFraOcrClient'

/** Catalogue / Library taxonomy for Fire Risk Assessment (filing categories). */
export const FRA_TAXONOMY_ID = '03.01'

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/**
 * Prefer the server-authoritative ``fra_ocr_eligible`` flag (template key OR
 * custom taxonomy 03.01, plus active + site-scoped). Taxonomy-only clientside
 * checks miss catalogue FRA rows whose taxonomy was edited away from 03.01.
 */
export function isFraOcrEligible(
  requirement: Pick<ComplianceRequirement, 'fra_ocr_eligible'>,
): boolean {
  return requirement.fra_ocr_eligible === true
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
