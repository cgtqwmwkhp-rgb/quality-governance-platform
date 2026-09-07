/**
 * One capture list, keyed by `captureId` (AUD-F6).
 *
 * Execute used to carry two arrays per answer: `photos: string[]` (preview URLs)
 * and `evidenceAssetIds: number[]` (upload ACKs), and treat entry *i* of one as
 * describing entry *i* of the other. Uploads are concurrent and can ACK out of
 * order, and a photo restored from the server starts with an id and no preview,
 * so the correspondence breaks in normal use: removing thumbnail 2 could
 * soft-delete the asset behind thumbnail 1.
 *
 * A capture is now one object with its own id. The id is minted on the device
 * before the upload is attempted, which is also what lets the device ledger store
 * the bytes under a key the answer record can name.
 *
 * The two old arrays survive only as *projections*, built by `evidenceViewOf` at
 * the moment a wire payload or a gate needs them — the same relationship AUD-F5
 * left between `audit_response_evidence` (the record) and
 * `response_json.evidence_asset_ids` (the projection). Nothing stores them.
 */
import type { AuditDraftCapture } from '../services/auditDraftStore'

export interface AuditCapture extends AuditDraftCapture {
  /**
   * `blob:`/`data:` URL for the thumbnail. In memory only: an object URL dies
   * with the document and a signed URL expires, so neither is persisted.
   */
  previewUrl?: string
}

/** What `PhotoCapture` renders: a thumbnail that knows which capture it is. */
export interface CapturePreview {
  captureId: string
  url: string
}

let captureCounter = 0

/**
 * A device-unique capture id.
 *
 * `crypto.randomUUID` where it exists (every browser this ships to). The
 * fallback still has to be unique *within a run on this device* — two photos
 * taken in the same millisecond must not collide — hence the counter as well as
 * the clock.
 */
export function newCaptureId(): string {
  const cryptoObj = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined
  if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
    return cryptoObj.randomUUID()
  }
  captureCounter += 1
  return `cap-${Date.now().toString(36)}-${captureCounter}-${Math.random().toString(36).slice(2, 8)}`
}

/**
 * The id for a capture the *server* already knows about, derived from its asset
 * id so re-reading the run does not mint a second capture for the same photo.
 */
export function serverCaptureId(evidenceAssetId: number): string {
  return `asset-${evidenceAssetId}`
}

export function photoCaptures(captures: AuditCapture[] | undefined): AuditCapture[] {
  return (captures ?? []).filter((capture) => capture.kind !== 'signature')
}

export function signatureCapture(captures: AuditCapture[] | undefined): AuditCapture | undefined {
  return (captures ?? []).find((capture) => capture.kind === 'signature')
}

/** Thumbnails for the photo captures that currently have something to show. */
export function capturePreviews(captures: AuditCapture[] | undefined): CapturePreview[] {
  return photoCaptures(captures)
    .filter((capture): capture is AuditCapture & { previewUrl: string } =>
      Boolean(capture.previewUrl),
    )
    .map((capture) => ({ captureId: capture.captureId, url: capture.previewUrl }))
}

/**
 * Persisted evidence ids across every capture on the answer.
 *
 * This is what the fail-evidence gate and the completion resolve read, so it
 * deliberately excludes captures the server has not ACKed: a photo sitting in
 * the device ledger is not evidence attached to the record.
 */
export function captureEvidenceIds(captures: AuditCapture[] | undefined): number[] {
  const ids: number[] = []
  for (const capture of captures ?? []) {
    const id = capture.evidenceAssetId
    if (typeof id === 'number' && id > 0 && !ids.includes(id)) ids.push(id)
  }
  return ids
}

export function appendCapture(
  captures: AuditCapture[] | undefined,
  capture: AuditCapture,
): AuditCapture[] {
  return [...(captures ?? []), capture]
}

export function removeCapture(
  captures: AuditCapture[] | undefined,
  captureId: string,
): AuditCapture[] {
  return (captures ?? []).filter((capture) => capture.captureId !== captureId)
}

/** Attach the upload ACK to the capture that produced it, by id — never by index. */
export function ackCapture(
  captures: AuditCapture[] | undefined,
  captureId: string,
  evidenceAssetId: number,
): AuditCapture[] {
  return (captures ?? []).map((capture) =>
    capture.captureId === captureId ? { ...capture, evidenceAssetId } : capture,
  )
}

export function setCapturePreview(
  captures: AuditCapture[] | undefined,
  captureId: string,
  previewUrl: string,
): AuditCapture[] {
  return (captures ?? []).map((capture) =>
    capture.captureId === captureId ? { ...capture, previewUrl } : capture,
  )
}

/**
 * Captures for evidence the server already holds.
 *
 * The id is derived from the asset id, so re-reading the run (or merging the
 * listed run evidence over the answer rows) cannot mint a second capture for a
 * photo that is already on screen. Captures the device holds and the server does
 * not — a failed upload — are carried through untouched.
 */
export function capturesFromAssetIds(
  assetIds: number[],
  questionType: string,
  capturedAt: string,
  existing?: AuditCapture[],
): AuditCapture[] {
  const kind: AuditCapture['kind'] = questionType === 'signature' ? 'signature' : 'photo'
  const captures = [...(existing ?? [])]
  const known = new Set(captureEvidenceIds(captures))
  for (const assetId of assetIds) {
    if (!(assetId > 0) || known.has(assetId)) continue
    known.add(assetId)
    captures.push({ captureId: serverCaptureId(assetId), kind, evidenceAssetId: assetId, capturedAt })
  }
  return captures
}

export function findCapture(
  captures: AuditCapture[] | undefined,
  captureId: string,
): AuditCapture | undefined {
  return (captures ?? []).find((capture) => capture.captureId === captureId)
}

/**
 * The legacy `{ photos, evidenceAssetIds }` shape, computed on demand.
 *
 * `auditAnswerIntegrity` and the fail-evidence gate keep taking this so their
 * behaviour (and the tests pinning it) stay exactly as AUD-F3/F4/F5 left them —
 * but no state holds it, so the two lists cannot drift apart.
 */
export function evidenceViewOf<
  TResponse extends {
    response: unknown
    notes?: string
    entityLabel?: string
    captures?: AuditCapture[]
  },
>(
  response: TResponse,
): {
  response: TResponse['response']
  notes?: string
  entityLabel?: string
  photos: string[]
  evidenceAssetIds: number[]
} {
  return {
    response: response.response,
    notes: response.notes,
    entityLabel: response.entityLabel,
    photos: capturePreviews(response.captures).map((preview) => preview.url),
    evidenceAssetIds: captureEvidenceIds(response.captures),
  }
}
