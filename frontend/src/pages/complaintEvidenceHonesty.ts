/**
 * Complaint detail evidence / downstream honesty (CMP-08).
 * Aligns portal reporter metadata with the shared evidence-assets spine and
 * clarifies investigation/actions downstream state.
 */

export function formatComplaintEvidenceRailSummary(options: {
  assetCount: number
  reporterPhotoCount: number
  assetsLoading?: boolean
  assetsFailed?: boolean
}): string {
  if (options.assetsLoading) return 'Loading evidence…'
  if (options.assetsFailed) {
    return options.reporterPhotoCount > 0
      ? `${options.reporterPhotoCount} reporter file name(s) (evidence assets unavailable)`
      : 'Evidence assets unavailable'
  }
  if (options.assetCount > 0) {
    return `${options.assetCount} evidence asset${options.assetCount === 1 ? '' : 's'}`
  }
  if (options.reporterPhotoCount > 0) {
    return `${options.reporterPhotoCount} reporter file name(s) — not on evidence spine`
  }
  return 'No evidence assets linked'
}

export function readReporterPhotoCount(submission: unknown): number {
  if (!submission || typeof submission !== 'object') return 0
  const photos = (submission as { photos?: unknown }).photos
  if (!photos || typeof photos !== 'object') return 0
  const count = (photos as { count?: unknown }).count
  return typeof count === 'number' && count > 0 ? count : 0
}

export function complaintDownstreamInvestigationHonesty(hasInvestigation: boolean): string {
  return hasInvestigation
    ? 'Linked investigation is the downstream workspace for CAPA.'
    : 'No investigation yet — start one to open the downstream CAPA workspace.'
}

export function complaintDownstreamActionsHonesty(openActionCount: number): string {
  if (openActionCount <= 0) {
    return 'No open actions — create actions from this complaint or the linked investigation.'
  }
  return `${openActionCount} open action${openActionCount === 1 ? '' : 's'} on this complaint.`
}
