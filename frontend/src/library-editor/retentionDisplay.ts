/**
 * CUT-1 / R19 retention, made readable on the Front Sheet.
 *
 * The backend resolves each taxonomy rule to `(years, anchor, basis)` or refuses
 * it by name, and a refusal leaves `retention_until` NULL because NULL is never a
 * disposal candidate — unreadable prose means keep, not destroy
 * (`src/domain/services/library_retention_policy.py`).
 *
 * This module carries that stance to the reader. It never infers a period, a
 * date or an anchor: absent is rendered as absent, and the absence is explained.
 */
import { formatLibraryDate } from './formatLibraryDate'
import type { LibraryBodyDocument, RetentionDisplay } from './types'

/** Mirrors `RetentionAnchor` — the event the period is measured from. */
export type LibraryRetentionAnchor = 'issue' | 'supersede' | 'event' | 'indefinite'

const ANCHORS: readonly LibraryRetentionAnchor[] = ['issue', 'supersede', 'event', 'indefinite']

const ANCHOR_PHRASE: Record<LibraryRetentionAnchor, string> = {
  issue: 'from issue',
  supersede: 'from supersede',
  event: 'from an event QGP does not hold',
  indefinite: 'indefinitely',
}

const NO_DATE_BY_ANCHOR: Record<LibraryRetentionAnchor, string> = {
  issue:
    'No disposal date is recorded on this document. Without a date it is never offered for disposal.',
  supersede:
    'No disposal date while this issue is current — the clock starts when it is superseded.',
  event:
    'The clock starts on an event QGP does not hold, so no disposal date can be calculated here.',
  indefinite: 'The current issue is kept indefinitely; there is no disposal date to calculate.',
}

function readAnchor(raw: string | null | undefined): LibraryRetentionAnchor | null {
  const value = (raw ?? '').trim().toLowerCase()
  return (ANCHORS as readonly string[]).includes(value) ? (value as LibraryRetentionAnchor) : null
}

function trimmedOrNull(raw: string | null | undefined): string | null {
  const value = (raw ?? '').trim()
  return value ? value : null
}

/**
 * Describe the retention position of one document. Total — every combination of
 * the four columns, including the ones the API should never emit together,
 * returns a statement a steward can act on.
 */
export function describeLibraryRetention(
  document: Pick<
    LibraryBodyDocument,
    'retention_until' | 'retention_years' | 'retention_anchor' | 'retention_basis'
  >,
): RetentionDisplay {
  const basis = trimmedOrNull(document.retention_basis)
  const disposalDate = formatLibraryDate(document.retention_until)
  const anchor = readAnchor(document.retention_anchor)
  const years =
    typeof document.retention_years === 'number' && Number.isFinite(document.retention_years)
      ? document.retention_years
      : null

  // `indefinite` and `event` are decided policies that carry no period by
  // design ("Keep the current issue", "Life of asset"), so a missing year count
  // is not an incomplete policy on those anchors — only on issue/supersede,
  // where the period is the whole rule.
  if (anchor && (anchor === 'indefinite' || anchor === 'event' || years !== null)) {
    let headline: string
    if (anchor === 'indefinite') {
      headline = 'Kept indefinitely'
    } else if (years === null) {
      headline = 'Retention runs from an event QGP does not hold'
    } else {
      headline = `${years} years ${ANCHOR_PHRASE[anchor]}`
    }

    let detail: string
    if (!disposalDate) {
      detail = NO_DATE_BY_ANCHOR[anchor]
    } else if (anchor === 'issue' || anchor === 'supersede') {
      detail = `Disposal review from ${disposalDate}.`
    } else {
      // The rule says no date is calculable, yet the row holds one. Show both
      // rather than hiding the disagreement behind whichever we prefer.
      detail = `${NO_DATE_BY_ANCHOR[anchor]} This row nonetheless carries a disposal date of ${disposalDate}; the rule, not the stored date, is the authority.`
    }

    return { headline, detail, disposalDate, basis, policyResolved: true }
  }

  // Everything below is a policy the register holds in pieces. Naming which
  // piece is missing matters: "no period" and "an anchor nobody validated" are
  // cleared by different people.
  if (anchor) {
    return {
      headline: 'Retention policy incomplete',
      detail: `The register holds a "${anchor}" anchor with no retention period, and the period is the whole rule on that anchor. No disposal date is calculated from half a policy.`,
      disposalDate,
      basis,
      policyResolved: false,
    }
  }

  // A stored anchor this build does not know is a disagreement between the API
  // and the page, not a licence to fall back to "issue".
  const unreadableAnchor = trimmedOrNull(document.retention_anchor)
  if (unreadableAnchor) {
    return {
      headline: 'Retention policy incomplete',
      detail: `The register holds an anchor this page does not recognise (${unreadableAnchor}), so no period is shown. No disposal date is calculated from an anchor nobody validated.`,
      disposalDate,
      basis,
      policyResolved: false,
    }
  }

  if (years !== null) {
    return {
      headline: 'Retention policy incomplete',
      detail:
        'The register holds a retention period with no anchor, so there is nothing to measure it from.',
      disposalDate,
      basis,
      policyResolved: false,
    }
  }

  if (disposalDate) {
    return {
      headline: 'Disposal date with no recorded policy',
      detail: `This row carries a disposal date of ${disposalDate} but not the rule it came from. Retention became machine-readable at CUT-1 and documents filed before it were deliberately not backfilled — deriving a policy now from today's taxonomy would be inventing an attestation.`,
      disposalDate,
      basis,
      policyResolved: false,
    }
  }

  if (basis) {
    return {
      headline: 'Retention rule not machine-readable',
      detail:
        'The governance rule names more than one period, or a condition the register does not record, so it was refused rather than guessed. A refused rule produces no disposal date, and a document with no date is never a disposal candidate.',
      disposalDate: null,
      basis,
      policyResolved: false,
    }
  }

  return {
    headline: 'No retention policy recorded',
    detail:
      'This document carries no retention policy. Documents filed before CUT-1 were not backfilled, so absence here means unknown — it is not permission to dispose.',
    disposalDate: null,
    basis: null,
    policyResolved: false,
  }
}
