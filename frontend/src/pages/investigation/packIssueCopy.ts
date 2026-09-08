/**
 * Status copy for issuing a customer pack (INV-C17).
 *
 * Plain English on the lazy Detail chunk — no en.json keys (212 kB gzip ceiling).
 * Mirrors the server blockers in investigation_pack_issue.py so the Report tab
 * can name the gate before the 422 arrives.
 */
import type { CustomerPackSummary } from '../../api/investigationsClient'

export const BLOCKER_NOT_COMPLETE = 'INVESTIGATION_NOT_COMPLETE'
export const BLOCKER_REDACTION_REVIEW_NOT_CLEARED = 'REDACTION_REVIEW_NOT_CLEARED'

const COMPLETE_STATUSES = new Set(['completed', 'closed'])

const BLOCKER_SENTENCE: Record<string, string> = {
  [BLOCKER_NOT_COMPLETE]: 'the investigation is not complete',
  [BLOCKER_REDACTION_REVIEW_NOT_CLEARED]: 'the redaction review has not been cleared',
}

export function isExternalPack(pack: Pick<CustomerPackSummary, 'audience'>): boolean {
  return pack.audience === 'external_customer'
}

export function investigationIsComplete(status: string | undefined): boolean {
  return COMPLETE_STATUSES.has(String(status || '').toLowerCase())
}

export function redactionReviewIsCleared(
  pack: Pick<CustomerPackSummary, 'redaction_review_cleared_at'>,
): boolean {
  return pack.redaction_review_cleared_at != null && pack.redaction_review_cleared_at !== ''
}

export function packIsIssued(pack: Pick<CustomerPackSummary, 'issued_at' | 'issued_pdf_sha256'>): boolean {
  return Boolean(pack.issued_at) || Boolean(pack.issued_pdf_sha256)
}

/** Reason codes that stop an *external* pack being issued, in report order. */
export function externalIssueBlockers(
  pack: Pick<CustomerPackSummary, 'audience' | 'redaction_review_cleared_at'>,
  investigationStatus: string | undefined,
): string[] {
  if (!isExternalPack(pack)) return []
  const blockers: string[] = []
  if (!investigationIsComplete(investigationStatus)) blockers.push(BLOCKER_NOT_COMPLETE)
  if (!redactionReviewIsCleared(pack)) blockers.push(BLOCKER_REDACTION_REVIEW_NOT_CLEARED)
  return blockers
}

export function issueBlockedSentence(blockers: string[]): string | null {
  if (blockers.length === 0) return null
  const reasons = blockers.map((code) => BLOCKER_SENTENCE[code] || code).join(' and ')
  return `This pack cannot be issued to a customer because ${reasons}.`
}

export function packIssueSummary(pack: CustomerPackSummary): string {
  const disclosures = pack.disclosure_count ?? 0
  if (packIsIssued(pack)) {
    const times = disclosures === 1 ? 'once' : `${disclosures} times`
    return disclosures > 0
      ? `Issued ${times}. Download returns the retained copy, not a live re-render.`
      : 'Issued. Download returns the retained copy, not a live re-render.'
  }
  if (isExternalPack(pack) && redactionReviewIsCleared(pack)) {
    return 'Redaction review cleared. Not yet issued to a customer.'
  }
  if (isExternalPack(pack)) {
    return 'Redaction review has not been cleared. Generating a pack is not the same as issuing it.'
  }
  return 'Internal pack. Issuing records who received it; it is not a customer disclosure gate.'
}
