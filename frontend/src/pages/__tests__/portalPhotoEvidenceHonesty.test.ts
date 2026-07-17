import { describe, expect, it } from 'vitest'
import {
  buildPortalPhotoMetadataSummary,
  isPortalPhotoMetadataOnly,
  portalPhotoEvidenceHonestyCopy,
} from '../portalPhotoEvidenceHonesty'

describe('portalPhotoEvidenceHonesty', () => {
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

  it('detects metadata-only reporter_submission photos', () => {
    expect(
      isPortalPhotoMetadataOnly({
        photos: { count: 1, evidence_spine: 'metadata_only', files: [] },
      }),
    ).toBe(true)
    expect(isPortalPhotoMetadataOnly({ photos: { count: 1 } })).toBe(false)
    expect(isPortalPhotoMetadataOnly(null)).toBe(false)
  })
})
