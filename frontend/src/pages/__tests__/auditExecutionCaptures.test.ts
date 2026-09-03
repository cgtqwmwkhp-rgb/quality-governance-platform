/**
 * AUD-F6 — one capture list, keyed by captureId.
 *
 * Execute used to keep `photos: string[]` and `evidenceAssetIds: number[]` side
 * by side and treat entry *i* of one as describing entry *i* of the other. These
 * cases are the two ways that assumption breaks in ordinary field use.
 */
import { describe, expect, it } from 'vitest'

import {
  ackCapture,
  appendCapture,
  captureEvidenceIds,
  capturePreviews,
  capturesFromAssetIds,
  evidenceViewOf,
  newCaptureId,
  photoCaptures,
  removeCapture,
  serverCaptureId,
  setCapturePreview,
  signatureCapture,
  type AuditCapture,
} from '../auditExecutionCaptures'

function photo(captureId: string, overrides: Partial<AuditCapture> = {}): AuditCapture {
  return {
    captureId,
    kind: 'photo',
    capturedAt: '2026-09-03T09:00:00Z',
    previewUrl: `blob:${captureId}`,
    ...overrides,
  }
}

describe('capture list', () => {
  it('mints ids that do not collide inside the same millisecond', () => {
    const ids = new Set(Array.from({ length: 200 }, () => newCaptureId()))
    expect(ids.size).toBe(200)
  })

  it('attaches an upload ACK to the capture that produced it, not to a position', () => {
    // Two photos in flight. The second one ACKs first, which is normal: it is
    // smaller, or the first request was retried.
    let captures = appendCapture(undefined, photo('first'))
    captures = appendCapture(captures, photo('second'))

    captures = ackCapture(captures, 'second', 502)
    captures = ackCapture(captures, 'first', 501)

    expect(captures.map((capture) => [capture.captureId, capture.evidenceAssetId])).toEqual([
      ['first', 501],
      ['second', 502],
    ])
    // The projection the wire and the gates read is order-independent.
    expect(captureEvidenceIds(captures).sort()).toEqual([501, 502])
  })

  it('removes the asset the auditor pointed at, even when an earlier capture has no preview yet', () => {
    // `first` is restored from the server and its thumbnail has not downloaded,
    // so it is not on screen. Under the old parallel arrays, deleting the only
    // visible thumbnail (index 0 of `photos`) soft-deleted `evidenceAssetIds[0]`
    // — which was the *other* photo.
    const captures = [
      photo('first', { previewUrl: undefined, evidenceAssetId: 501 }),
      photo('second', { evidenceAssetId: 502 }),
    ]

    const onScreen = capturePreviews(captures)
    expect(onScreen).toEqual([{ captureId: 'second', url: 'blob:second' }])

    const next = removeCapture(captures, onScreen[0].captureId)
    expect(captureEvidenceIds(next)).toEqual([501])
  })

  it('treats a capture the device holds but the server has not ACKed as not evidence', () => {
    const captures = [photo('local'), photo('acked', { evidenceAssetId: 700 })]
    // The fail-evidence gate and the completion resolve both read this list, and
    // a photo sitting in the device ledger is not attached to the record.
    expect(captureEvidenceIds(captures)).toEqual([700])
  })

  it('keeps signature and photo captures in one list but tells them apart', () => {
    const captures = [photo('p1'), { ...photo('s1'), kind: 'signature' as const }]
    expect(photoCaptures(captures).map((capture) => capture.captureId)).toEqual(['p1'])
    expect(signatureCapture(captures)?.captureId).toBe('s1')
    // A signature is never a photo thumbnail.
    expect(capturePreviews(captures).map((preview) => preview.captureId)).toEqual(['p1'])
  })

  it('sets a hydrated preview on one capture without disturbing the others', () => {
    const captures = [photo('a', { previewUrl: undefined }), photo('b')]
    const next = setCapturePreview(captures, 'a', 'blob:hydrated')
    expect(next[0].previewUrl).toBe('blob:hydrated')
    expect(next[1].previewUrl).toBe('blob:b')
  })

  it('does not mint a second capture for a photo the server already reported', () => {
    const first = capturesFromAssetIds([501, 502], 'photo', '2026-09-03T09:00:00Z')
    expect(first.map((capture) => capture.captureId)).toEqual([
      serverCaptureId(501),
      serverCaptureId(502),
    ])

    // The AUD-F2 merge of listed run evidence runs over the same answer.
    const merged = capturesFromAssetIds([501, 502, 503], 'photo', '2026-09-03T09:00:00Z', first)
    expect(captureEvidenceIds(merged)).toEqual([501, 502, 503])
    expect(merged).toHaveLength(3)
  })

  it('carries an unsynced local capture through a server merge', () => {
    const existing = [photo('local-only')]
    const merged = capturesFromAssetIds([501], 'photo', '2026-09-03T09:00:00Z', existing)
    expect(merged.map((capture) => capture.captureId)).toEqual(['local-only', serverCaptureId(501)])
  })

  it('projects the legacy wire shape without storing it', () => {
    const view = evidenceViewOf({
      response: 'captured' as const,
      notes: 'guard missing',
      entityLabel: 'Jamie Okonkwo',
      captures: [photo('a', { evidenceAssetId: 501 })],
    })
    expect(view).toEqual({
      response: 'captured',
      notes: 'guard missing',
      entityLabel: 'Jamie Okonkwo',
      photos: ['blob:a'],
      evidenceAssetIds: [501],
    })
  })
})
