import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildPortalPhotoMetadataSummary,
  isAllowedPortalPhoto,
  isPortalPhotoMetadataOnly,
  MAX_PORTAL_PHOTO_COUNT,
  portalPhotoEvidenceHonestyCopy,
  portalPhotoPreviewUrl,
  validatePortalPhotos,
} from '../portalPhotoEvidenceHonesty'

describe('portalPhotoEvidenceHonesty', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('builds metadata-only photo summary with evidence_spine flag', () => {
    const file = new File(['x'], 'scene.jpg', { type: 'image/jpeg' })
    const summary = buildPortalPhotoMetadataSummary([file])
    expect(summary.count).toBe(1)
    expect(summary.evidence_spine).toBe('metadata_only')
    expect(summary.files[0]).toEqual({
      name: 'scene.jpg',
      type: 'image/jpeg',
      size: 1,
    })
  })

  it('returns honest copy for zero and non-zero photo counts', () => {
    expect(portalPhotoEvidenceHonestyCopy(0)).toMatch(/No photos selected/i)
    expect(portalPhotoEvidenceHonestyCopy(2)).toMatch(/not uploaded to the shared evidence store/i)
    expect(portalPhotoEvidenceHonestyCopy(2)).toMatch(/2 photo filename/)
  })

  it('builds preview URLs from a Blob copy of the file', () => {
    const createObjectURL = vi.fn(() => 'blob:portal-preview')
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() })
    const file = new File(['x'], 'scene.jpg', { type: 'image/jpeg' })
    expect(portalPhotoPreviewUrl(file)).toBe('blob:portal-preview')
    expect(createObjectURL).toHaveBeenCalledTimes(1)
    const arg = createObjectURL.mock.calls[0]?.[0]
    expect(arg).toBeInstanceOf(Blob)
    expect(arg).not.toBe(file)
    expect((arg as Blob).type).toBe('image/jpeg')
  })

  it('detects metadata-only reporter_submission photos', () => {
    expect(
      isPortalPhotoMetadataOnly({
        photos: { count: 1, evidence_spine: 'metadata_only', files: [] },
      }),
    ).toBe(true)
    expect(isPortalPhotoMetadataOnly({ photos: { count: 1 } })).toBe(false)
    expect(isPortalPhotoMetadataOnly(null)).toBe(false)
  })

  it('rejects non-images and oversize files (PX-325)', () => {
    const pdf = new File(['x'], 'notes.pdf', { type: 'application/pdf' })
    const huge = new File([new Uint8Array(11 * 1024 * 1024)], 'big.jpg', {
      type: 'image/jpeg',
    })
    const ok = new File(['x'], 'ok.jpg', { type: 'image/jpeg' })
    expect(isAllowedPortalPhoto(pdf)).toBe(false)
    const result = validatePortalPhotos([pdf, huge, ok], [])
    expect(result.accepted).toHaveLength(1)
    expect(result.accepted[0].name).toBe('ok.jpg')
    expect(result.errors.length).toBeGreaterThanOrEqual(2)
  })

  it('enforces max photo count and skips duplicates (PX-325)', () => {
    const existing = Array.from(
      { length: MAX_PORTAL_PHOTO_COUNT - 1 },
      (_, i) => new File(['x'], `e${i}.jpg`, { type: 'image/jpeg' }),
    )
    const dup = existing[0]
    const next = new File(['y'], 'next.jpg', { type: 'image/jpeg' })
    const overflow = new File(['z'], 'overflow.jpg', { type: 'image/jpeg' })
    const result = validatePortalPhotos([dup, next, overflow], existing)
    expect(result.accepted.map((f) => f.name)).toEqual(['next.jpg'])
    expect(result.errors.some((e) => /already attached/i.test(e))).toBe(true)
    expect(result.errors.some((e) => /up to/i.test(e))).toBe(true)
  })
})
