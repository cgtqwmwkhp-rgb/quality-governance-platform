/**
 * Portal photo upload honesty helpers (EVD-02).
 *
 * Public portal submit currently persists photo filename/size metadata in
 * reporter_submission only — binary files are not yet written to the shared
 * evidence-assets spine. Staff can attach real evidence after triage.
 */

export type PortalPhotoMeta = {
  name: string
  type: string
  size: number
}

export function buildPortalPhotoMetadataSummary(photos: ReadonlyArray<File>): {
  count: number
  files: PortalPhotoMeta[]
  evidence_spine: 'metadata_only'
} {
  return {
    count: photos.length,
    files: photos.map((photo) => ({
      name: photo.name,
      type: photo.type,
      size: photo.size,
    })),
    evidence_spine: 'metadata_only',
  }
}

export function portalPhotoEvidenceHonestyCopy(photoCount: number): string {
  if (photoCount <= 0) {
    return 'No photos selected. You can still submit — staff may request evidence later.'
  }
  return (
    `${photoCount} photo filename(s) will be recorded with this report. ` +
    'Binary files are not uploaded to the shared evidence store from the portal yet — ' +
    'staff can attach evidence on the case record after triage.'
  )
}

export function isPortalPhotoMetadataOnly(submission: unknown): boolean {
  if (!submission || typeof submission !== 'object') return false
  const photos = (submission as { photos?: unknown }).photos
  if (!photos || typeof photos !== 'object') return false
  return (photos as { evidence_spine?: unknown }).evidence_spine === 'metadata_only'
}
