/**
 * Portal photo upload honesty helpers (EVD-02) + client validation (PX-325/326).
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

/** Per-file size cap for portal intake photos (PX-325). */
export const MAX_PORTAL_PHOTO_BYTES = 10 * 1024 * 1024

/** Hard cap on photos attached to one portal report (PX-325). */
export const MAX_PORTAL_PHOTO_COUNT = 8

const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif', 'bmp']

export function formatPortalPhotoSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)}KB`
  return `${bytes} bytes`
}

function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : ''
}

export function isAllowedPortalPhoto(file: File): boolean {
  const extension = fileExtension(file.name)
  return file.type.startsWith('image/') || IMAGE_EXTENSIONS.includes(extension)
}

export type PortalPhotoValidationResult = {
  accepted: File[]
  errors: string[]
}

/**
 * Validate newly selected photos against type, size, and count limits before
 * appending them to form state (PX-325). Duplicate name+size pairs are skipped.
 */
export function validatePortalPhotos(
  incoming: File[],
  existing: ReadonlyArray<File>,
  options?: { maxBytes?: number; maxCount?: number },
): PortalPhotoValidationResult {
  const maxBytes = options?.maxBytes ?? MAX_PORTAL_PHOTO_BYTES
  const maxCount = options?.maxCount ?? MAX_PORTAL_PHOTO_COUNT
  const accepted: File[] = []
  const errors: string[] = []
  const seen = new Set(existing.map((file) => `${file.name}:${file.size}`))

  for (const file of incoming) {
    const key = `${file.name}:${file.size}`
    if (seen.has(key)) {
      errors.push(`"${file.name}" is already attached.`)
      continue
    }
    if (!isAllowedPortalPhoto(file)) {
      errors.push(
        `"${file.name}" is not an image. Upload a JPG, PNG, GIF, WEBP or HEIC file.`,
      )
      continue
    }
    if (file.size > maxBytes) {
      errors.push(
        `"${file.name}" is ${formatPortalPhotoSize(file.size)}, which is over the ${formatPortalPhotoSize(maxBytes)} limit.`,
      )
      continue
    }
    if (existing.length + accepted.length >= maxCount) {
      errors.push(`You can attach up to ${maxCount} photos per report.`)
      break
    }
    seen.add(key)
    accepted.push(file)
  }

  return { accepted, errors }
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
