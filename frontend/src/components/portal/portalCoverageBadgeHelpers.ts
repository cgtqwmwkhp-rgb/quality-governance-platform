/**
 * Library WK-1 / L-48 — portal CURRENT coverage badge helpers.
 *
 * Scaffold only: display math for issue currency on PortalReading.
 * No editor chrome. API field `document_issue_state` may arrive later;
 * until then callers pass optional state (or omit → UNKNOWN).
 */

export type PortalDocumentIssueState = 'CURRENT' | 'SUPERSEDED' | 'DRAFT' | 'UNKNOWN'

export type PortalCoverageBadgeVariant =
  | 'success'
  | 'warning'
  | 'secondary'
  | 'outline'

export interface PortalCoverageBadgeModel {
  state: PortalDocumentIssueState
  labelKey: string
  variant: PortalCoverageBadgeVariant
  /** When false, render nothing (unknown + no version hint). */
  visible: boolean
}

export interface PortalCoverageBadgeSource {
  document_issue_state?: string | null
  document_version?: string | null
}

function normalizeIssueState(raw: string | null | undefined): PortalDocumentIssueState {
  if (!raw || !String(raw).trim()) return 'UNKNOWN'
  const value = String(raw).trim().toUpperCase().replace(/\s+/g, '_')
  if (value === 'CURRENT' || value === 'LIVE' || value === 'PUBLISHED') return 'CURRENT'
  if (value === 'SUPERSEDED' || value === 'OBSOLETE' || value === 'RETIRED') return 'SUPERSEDED'
  if (value === 'DRAFT' || value === 'PENDING' || value === 'IN_REVIEW') return 'DRAFT'
  return 'UNKNOWN'
}

/**
 * Resolve portal coverage badge for a reading assignment.
 * Prefer explicit issue state; never invent CURRENT from version alone.
 */
export function resolvePortalCoverageBadge(
  source: PortalCoverageBadgeSource | null | undefined,
): PortalCoverageBadgeModel {
  const state = normalizeIssueState(source?.document_issue_state)
  if (state === 'CURRENT') {
    return {
      state,
      labelKey: 'portal_reading.coverage_badge.current',
      variant: 'success',
      visible: true,
    }
  }
  if (state === 'SUPERSEDED') {
    return {
      state,
      labelKey: 'portal_reading.coverage_badge.superseded',
      variant: 'warning',
      visible: true,
    }
  }
  if (state === 'DRAFT') {
    return {
      state,
      labelKey: 'portal_reading.coverage_badge.draft',
      variant: 'secondary',
      visible: true,
    }
  }
  // UNKNOWN: show a muted version chip only when a version string exists.
  if (source?.document_version && String(source.document_version).trim()) {
    return {
      state: 'UNKNOWN',
      labelKey: 'portal_reading.coverage_badge.version_only',
      variant: 'outline',
      visible: true,
    }
  }
  return {
    state: 'UNKNOWN',
    labelKey: 'portal_reading.coverage_badge.unknown',
    variant: 'outline',
    visible: false,
  }
}
