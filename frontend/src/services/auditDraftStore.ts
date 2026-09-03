/**
 * auditDraftStore — the audit **device ledger** (AUD-F6).
 *
 * What this is: the honest record of what an auditor has entered that the server
 * does not have yet, on the device they entered it on.
 *
 * What this is **not**:
 *   - It is not the photo source of truth. Azure plus `audit_response_evidence`
 *     (AUD-F5) is. Once a capture is ACKed by the server its bytes are dropped
 *     from here, because a second copy of something the record already holds
 *     only costs the auditor quota they need for the next photo.
 *   - It is not an outbox. Nothing here replays a write. The ledger lets an
 *     auditor get their answers back; pressing Save is still what puts them on
 *     the server.
 *
 * Three defects this shape exists to remove, all of them live before AUD-F6:
 *
 * 1. **Keyed by `runId` alone.** A field tablet is shared. The next auditor to
 *    open the same run was offered the previous auditor's answers and could
 *    restore them over their own. Every row is now prefixed with
 *    `t{tenant}:u{user}` (see `deviceLedgerIdentity.ts`), and a deliberate
 *    sign-out purges that prefix.
 *
 * 2. **Photos as data-URL strings inside the answer record.** Autosave rewrote
 *    the whole record — every photo, base64-inflated by a third — on every tick.
 *    Answers and bytes are now separate stores: the ledger record holds capture
 *    *identity* only, and `putCaptureBlob` is the one and only writer of bytes.
 *    A blob is written once, when the capture happens. `saveAuditDraft` cannot
 *    rewrite a blob because it never opens that store.
 *
 * 3. **`QuotaExceeded` swallowed into `return false`.** Nothing in the UI said
 *    the draft had not been stored, so a full device looked identical to a
 *    working one. Writes now return why they failed and publish it to
 *    `subscribeDeviceLedgerStatus`, which the execute page renders as a blocking
 *    banner. The same channel carries the `persist()` verdict: if the browser
 *    refuses durable storage the page says this audit is not durable on this
 *    device, rather than implying it will sync.
 *
 * Deliberately not stored: signed URLs (they expire, and a stale SAS in
 * IndexedDB is a support call), and entity pick-list labels — a staff or
 * customer *name* is PII with no business being cached on a shared tablet.
 * `sanitiseQuestion` strips both on the way in, so a caller cannot leak them by
 * spreading its own state into a draft.
 */
import { openDB, type IDBPDatabase, type DBSchema } from 'idb'

import {
  clearDeviceLedgerIdentity,
  deviceLedgerNamespace,
  getDeviceLedgerIdentity,
} from './deviceLedgerIdentity'

const DB_NAME = 'qgp-audit-drafts'
/** v1 was `drafts`, keyPath `runId`, photos inline. v2 replaces it outright. */
const DB_VERSION = 2
const LEGACY_STORE = 'drafts'
const LEDGER_STORE = 'ledger'
const BLOB_STORE = 'blobs'

/**
 * Key separator. Namespaces are `t{int}:u{int}` and capture ids are generated
 * without `:`, so `::` cannot appear inside a segment and a prefix match cannot
 * straddle two segments (`t1:u2` never prefixes `t1:u21`).
 */
const KEY_SEP = '::'

/**
 * A ledger record older than this is not worth restoring — the run has almost
 * certainly moved on server-side, and offering fortnight-old answers as
 * "unsaved" invites an auditor to overwrite the real record. Cheap to enforce:
 * checked on the read that finds it, which is the only moment it matters.
 */
export const DRAFT_TTL_MS = 14 * 24 * 60 * 60 * 1000

// ---------------------------------------------------------------------------
// Public shapes
// ---------------------------------------------------------------------------

/**
 * One capture, as the ledger stores it: identity, not bytes and not a URL.
 *
 * `captureId` is minted on the device the moment the auditor takes or picks the
 * photo, and it is the only thing tying the answer record to the bytes in the
 * blob store. Parallel `photos[]` / `evidenceAssetIds[]` arrays — two lists
 * whose entries correspond by index and stop corresponding the first time an
 * upload finishes out of order — are the bug this replaces.
 */
export interface AuditDraftCapture {
  captureId: string
  kind: 'photo' | 'signature'
  /** Set once the AUD-F5 capture endpoint ACKed. Absent means server-unaware. */
  evidenceAssetId?: number
  capturedAt: string
}

export interface AuditDraftQuestion {
  questionId: string
  response: unknown
  notes?: string
  captures?: AuditDraftCapture[]
  flagged?: boolean
  timestamp: string
  duration?: number
}

export interface AuditDraft {
  runId: number
  responses: Record<string, AuditDraftQuestion>
  responseIdMap: Record<string, number>
  currentSectionIndex: number
  currentQuestionIndex: number
  savedAt: number
  reason: 'autosave' | 'auth-loss' | 'manual'
}

export type DeviceLedgerFailureReason =
  | 'indexeddb-unavailable'
  | 'no-identity'
  | 'quota-exceeded'
  | 'write-failed'

export type DeviceLedgerReason =
  | 'ok'
  | 'persist-denied'
  | 'persist-unsupported'
  | DeviceLedgerFailureReason

/** What a ledger write actually did. Never a bare boolean. */
export type DraftWriteResult =
  | { ok: true }
  | { ok: false; reason: DeviceLedgerFailureReason; message: string }

export interface DeviceLedgerStatus {
  /** True only when this device will hold answers the server has not got. */
  durable: boolean
  reason: DeviceLedgerReason
  /** Auditor-facing copy. Never promises a sync that does not exist. */
  message: string
  /**
   * True when a write was attempted and did not land. Distinct from `!durable`,
   * which can mean "the browser will not promise to keep what we did write".
   */
  writeFailed: boolean
  usageBytes: number | null
  quotaBytes: number | null
}

const MESSAGES: Record<DeviceLedgerReason, string> = {
  ok: '',
  'indexeddb-unavailable':
    'This audit is not durable on this device: the browser will not store anything locally. Stay online and press Save after every few answers.',
  'no-identity':
    'This audit is not durable on this device: the app cannot tell which account it belongs to, so nothing is stored locally. Stay online and press Save.',
  'persist-denied':
    'This audit is not durable on this device: the browser refused durable storage and may clear these answers without warning. Press Save while you have signal.',
  'persist-unsupported':
    'This audit is not durable on this device: the browser cannot promise to keep local answers. Press Save while you have signal.',
  'quota-exceeded':
    'Device storage is full — this answer was NOT saved on this device. Free up space, then press Save while you have signal.',
  'write-failed':
    'Saving to this device failed — nothing was stored locally for this audit. Press Save while you have signal.',
}

// ---------------------------------------------------------------------------
// Storage schema
// ---------------------------------------------------------------------------

interface AuditDraftRecord extends AuditDraft {
  /** `{namespace}::r{runId}` */
  key: string
  namespace: string
}

interface CaptureBlobRecord {
  /** `{namespace}::r{runId}::c{captureId}` */
  key: string
  namespace: string
  runId: number
  captureId: string
  questionId: string
  kind: 'photo' | 'signature'
  blob: Blob
  savedAt: number
}

interface AuditLedgerSchema extends DBSchema {
  /**
   * The v1 store, declared only so the v2 upgrade can name it in
   * `deleteObjectStore`. Nothing reads it.
   */
  drafts: { key: number; value: unknown }
  ledger: { key: string; value: AuditDraftRecord }
  blobs: { key: string; value: CaptureBlobRecord }
}

let dbPromise: Promise<IDBPDatabase<AuditLedgerSchema>> | null = null

function isIndexedDbAvailable(): boolean {
  try {
    return (
      typeof indexedDB !== 'undefined' &&
      indexedDB !== null &&
      typeof (indexedDB as IDBFactory).open === 'function'
    )
  } catch {
    return false
  }
}

async function getDb(): Promise<IDBPDatabase<AuditLedgerSchema> | null> {
  if (!isIndexedDbAvailable()) return null
  if (!dbPromise) {
    dbPromise = openDB<AuditLedgerSchema>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        // v1 records were keyed by run id alone, held photos as inline data
        // URLs, and carried entity labels. Migrating them would mean deciding
        // which auditor each one belongs to — precisely the fact that was never
        // recorded. They are dropped rather than guessed at.
        if (db.objectStoreNames.contains(LEGACY_STORE)) {
          db.deleteObjectStore(LEGACY_STORE)
        }
        if (!db.objectStoreNames.contains(LEDGER_STORE)) {
          db.createObjectStore(LEDGER_STORE, { keyPath: 'key' })
        }
        if (!db.objectStoreNames.contains(BLOB_STORE)) {
          db.createObjectStore(BLOB_STORE, { keyPath: 'key' })
        }
      },
    })
  }
  try {
    return await dbPromise
  } catch {
    dbPromise = null
    return null
  }
}

/** Test hook — drop the cached connection so a fresh `openDB` runs. */
export function resetDeviceLedgerConnection(): void {
  dbPromise = null
}

// ---------------------------------------------------------------------------
// Keys and namespacing
// ---------------------------------------------------------------------------

export function currentLedgerNamespace(): string | null {
  const identity = getDeviceLedgerIdentity()
  return identity ? deviceLedgerNamespace(identity) : null
}

function runPrefix(namespace: string, runId: number): string {
  return `${namespace}${KEY_SEP}r${runId}`
}

function ledgerKey(namespace: string, runId: number): string {
  return runPrefix(namespace, runId)
}

function blobKey(namespace: string, runId: number, captureId: string): string {
  return `${runPrefix(namespace, runId)}${KEY_SEP}c${captureId}`
}

// ---------------------------------------------------------------------------
// Durability status
// ---------------------------------------------------------------------------

const OK_STATUS: DeviceLedgerStatus = {
  durable: true,
  reason: 'ok',
  message: '',
  writeFailed: false,
  usageBytes: null,
  quotaBytes: null,
}

let status: DeviceLedgerStatus = OK_STATUS
const statusListeners = new Set<(next: DeviceLedgerStatus) => void>()

function publish(next: DeviceLedgerStatus): DeviceLedgerStatus {
  const changed =
    next.durable !== status.durable ||
    next.reason !== status.reason ||
    next.writeFailed !== status.writeFailed ||
    next.usageBytes !== status.usageBytes ||
    next.quotaBytes !== status.quotaBytes
  status = next
  if (changed) {
    for (const listener of statusListeners) {
      try {
        listener(next)
      } catch {
        // One bad subscriber must not stop the others, and must never propagate
        // into the save path that reported the failure.
      }
    }
  }
  return next
}

export function getDeviceLedgerStatus(): DeviceLedgerStatus {
  return status
}

export function subscribeDeviceLedgerStatus(
  listener: (next: DeviceLedgerStatus) => void,
): () => void {
  statusListeners.add(listener)
  return () => {
    statusListeners.delete(listener)
  }
}

/** Test hook — forget the published status and its subscribers. */
export function resetDeviceLedgerStatus(): void {
  status = OK_STATUS
  statusListeners.clear()
}

function reportFailure(reason: DeviceLedgerFailureReason): DraftWriteResult {
  publish({
    durable: false,
    reason,
    message: MESSAGES[reason],
    // A write was attempted and did not land — the auditor must be told, not
    // reassured. This is the flag the execute page renders as a blocking alert.
    writeFailed: true,
    usageBytes: status.usageBytes,
    quotaBytes: status.quotaBytes,
  })
  return { ok: false, reason, message: MESSAGES[reason] }
}

function reportWriteSucceeded(): void {
  if (status.writeFailed) {
    // A later write landing does not retroactively make the browser promise
    // durability, so only the "this did not save" part is cleared.
    publish({ ...status, writeFailed: false })
  }
}

function isQuotaError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const name = (error as { name?: unknown }).name
  if (name === 'QuotaExceededError' || name === 'NS_ERROR_DOM_QUOTA_REACHED') return true
  // Legacy DOMException code for quota, still what older WebKit reports.
  if ((error as { code?: unknown }).code === 22) return true
  const message = (error as { message?: unknown }).message
  return typeof message === 'string' && /quota/i.test(message)
}

function failureFor(error: unknown): DeviceLedgerFailureReason {
  return isQuotaError(error) ? 'quota-exceeded' : 'write-failed'
}

interface StorageManagerLike {
  persisted?: () => Promise<boolean>
  persist?: () => Promise<boolean>
  estimate?: () => Promise<{ usage?: number; quota?: number }>
}

function storageManager(): StorageManagerLike | undefined {
  if (typeof navigator === 'undefined') return undefined
  return (navigator as Navigator & { storage?: StorageManagerLike }).storage
}

/**
 * Ask the browser to keep this origin's storage, and report honestly when it
 * will not.
 *
 * `persist()` being denied is not a failure to work around — Safari and any
 * browser in private mode will refuse — it is a fact the auditor needs, because
 * it means the answers on screen can vanish when the OS reclaims space. The
 * published copy therefore says the audit is *not* durable on this device and
 * tells them to press Save; it never says anything will sync.
 */
export async function ensureDeviceLedgerDurability(): Promise<DeviceLedgerStatus> {
  const db = await getDb()
  if (!db) {
    return publish({
      durable: false,
      reason: 'indexeddb-unavailable',
      message: MESSAGES['indexeddb-unavailable'],
      writeFailed: false,
      usageBytes: null,
      quotaBytes: null,
    })
  }

  if (!currentLedgerNamespace()) {
    return publish({
      durable: false,
      reason: 'no-identity',
      message: MESSAGES['no-identity'],
      writeFailed: false,
      usageBytes: null,
      quotaBytes: null,
    })
  }

  const storage = storageManager()

  let persisted: boolean | null = null
  if (typeof storage?.persisted === 'function') {
    try {
      persisted = await storage.persisted()
    } catch {
      persisted = null
    }
  }
  if (persisted === false && typeof storage?.persist === 'function') {
    try {
      persisted = await storage.persist()
    } catch {
      persisted = false
    }
  }

  let usageBytes: number | null = null
  let quotaBytes: number | null = null
  if (typeof storage?.estimate === 'function') {
    try {
      const estimate = await storage.estimate()
      usageBytes = typeof estimate?.usage === 'number' ? estimate.usage : null
      quotaBytes = typeof estimate?.quota === 'number' ? estimate.quota : null
    } catch {
      /* an unreadable estimate is not itself a durability verdict */
    }
  }

  if (persisted === null) {
    return publish({
      durable: false,
      reason: 'persist-unsupported',
      message: MESSAGES['persist-unsupported'],
      writeFailed: status.writeFailed,
      usageBytes,
      quotaBytes,
    })
  }
  if (!persisted) {
    return publish({
      durable: false,
      reason: 'persist-denied',
      message: MESSAGES['persist-denied'],
      writeFailed: status.writeFailed,
      usageBytes,
      quotaBytes,
    })
  }

  return publish({
    durable: true,
    reason: 'ok',
    message: '',
    writeFailed: status.writeFailed,
    usageBytes,
    quotaBytes,
  })
}

// ---------------------------------------------------------------------------
// Answer ledger
// ---------------------------------------------------------------------------

/**
 * Strip everything that must not reach the device.
 *
 * Enforced here rather than trusted to callers: the execute page keeps preview
 * URLs and entity labels on the same in-memory answer object it snapshots, so
 * "the caller will remember not to include them" is not a control.
 */
function sanitiseQuestion(question: AuditDraftQuestion): AuditDraftQuestion {
  const captures = (question.captures ?? [])
    .filter((capture) => Boolean(capture?.captureId))
    .map((capture) => ({
      captureId: capture.captureId,
      kind: capture.kind === 'signature' ? ('signature' as const) : ('photo' as const),
      capturedAt: capture.capturedAt,
      // A preview URL is either a signed URL that expires or an object URL that
      // dies with the document. Neither is worth a row.
      ...(typeof capture.evidenceAssetId === 'number' && capture.evidenceAssetId > 0
        ? { evidenceAssetId: capture.evidenceAssetId }
        : {}),
    }))

  return {
    questionId: question.questionId,
    // The entity *id* is the answer and is kept. The label is a staff or
    // customer name — pick-list PII, which is not cached on a shared device.
    response: question.response,
    ...(question.notes !== undefined ? { notes: question.notes } : {}),
    ...(captures.length > 0 ? { captures } : {}),
    ...(question.flagged !== undefined ? { flagged: question.flagged } : {}),
    timestamp: question.timestamp,
    ...(question.duration !== undefined ? { duration: question.duration } : {}),
  }
}

function sanitiseDraft(draft: AuditDraft): AuditDraft {
  const responses: Record<string, AuditDraftQuestion> = {}
  for (const [questionId, question] of Object.entries(draft.responses || {})) {
    if (!question) continue
    responses[questionId] = sanitiseQuestion(question)
  }
  return {
    runId: draft.runId,
    responses,
    responseIdMap: { ...draft.responseIdMap },
    currentSectionIndex: draft.currentSectionIndex,
    currentQuestionIndex: draft.currentQuestionIndex,
    savedAt: draft.savedAt,
    reason: draft.reason,
  }
}

/**
 * Write the answer ledger for one run.
 *
 * Touches `ledger` and nothing else. Autosave calls this every tick, so it must
 * not be able to rewrite a single byte of photo — the blob store is not opened
 * here, which makes that structural rather than a rule someone has to keep.
 *
 * `namespace` is only passed by the auth-loss flush, which resolves it
 * synchronously before the access token is cleared out from under it.
 */
export async function saveAuditDraft(
  draft: AuditDraft,
  namespace?: string,
): Promise<DraftWriteResult> {
  const db = await getDb()
  if (!db) return reportFailure('indexeddb-unavailable')

  const scope = namespace ?? currentLedgerNamespace()
  if (!scope) return reportFailure('no-identity')

  const record: AuditDraftRecord = {
    ...sanitiseDraft(draft),
    key: ledgerKey(scope, draft.runId),
    namespace: scope,
  }

  try {
    await db.put(LEDGER_STORE, record)
    reportWriteSucceeded()
    return { ok: true }
  } catch (error) {
    return reportFailure(failureFor(error))
  }
}

export async function getAuditDraft(runId: number): Promise<AuditDraft | null> {
  const db = await getDb()
  if (!db) return null
  const scope = currentLedgerNamespace()
  if (!scope) return null
  try {
    const record = await db.get(LEDGER_STORE, ledgerKey(scope, runId))
    if (!record) return null
    if (Date.now() - record.savedAt > DRAFT_TTL_MS) {
      // Expired drafts go on the read that found them: no sweeper, no timer, and
      // no chance of offering fortnight-old answers as "unsaved".
      await deleteAuditDraft(runId)
      return null
    }
    const { key: _key, namespace: _namespace, ...draft } = record
    return draft
  } catch {
    return null
  }
}

/**
 * Drop one run's ledger record and every capture blob it owns.
 *
 * Called when a server save has demonstrably landed every attempted answer, so
 * the bytes are on the record and this device has nothing left to hold.
 */
export async function deleteAuditDraft(runId: number): Promise<void> {
  const db = await getDb()
  if (!db) return
  const scope = currentLedgerNamespace()
  if (!scope) return
  try {
    await db.delete(LEDGER_STORE, ledgerKey(scope, runId))
    await deleteBlobsWithPrefix(db, `${runPrefix(scope, runId)}${KEY_SEP}`)
  } catch {
    /* a ledger that cannot be tidied is not a reason to fail the save */
  }
}

export async function listAuditDrafts(): Promise<AuditDraft[]> {
  const db = await getDb()
  if (!db) return []
  const scope = currentLedgerNamespace()
  if (!scope) return []
  try {
    const records = await db.getAll(LEDGER_STORE)
    return records
      .filter((record) => record.namespace === scope)
      .filter((record) => Date.now() - record.savedAt <= DRAFT_TTL_MS)
      .map(({ key: _key, namespace: _namespace, ...draft }) => draft)
  } catch {
    return []
  }
}

// ---------------------------------------------------------------------------
// Capture blobs
// ---------------------------------------------------------------------------

/**
 * Store the bytes of one capture, once.
 *
 * The only writer of the blob store. Called at the moment the auditor takes or
 * picks the photo, *before* the upload is attempted, so a failed upload still
 * leaves the photo recoverable. Deleted again by `deleteCaptureBlob` as soon as
 * the server ACKs, because from that point the AUD-F5 join is the record and a
 * second copy is only quota the auditor needs for the next photo.
 */
export async function putCaptureBlob(input: {
  runId: number
  captureId: string
  questionId: string
  kind: 'photo' | 'signature'
  blob: Blob
}): Promise<DraftWriteResult> {
  const db = await getDb()
  if (!db) return reportFailure('indexeddb-unavailable')
  const scope = currentLedgerNamespace()
  if (!scope) return reportFailure('no-identity')

  const record: CaptureBlobRecord = {
    key: blobKey(scope, input.runId, input.captureId),
    namespace: scope,
    runId: input.runId,
    captureId: input.captureId,
    questionId: input.questionId,
    kind: input.kind,
    blob: input.blob,
    savedAt: Date.now(),
  }

  try {
    await db.put(BLOB_STORE, record)
    reportWriteSucceeded()
    return { ok: true }
  } catch (error) {
    return reportFailure(failureFor(error))
  }
}

export interface StoredCapture {
  captureId: string
  questionId: string
  kind: 'photo' | 'signature'
  blob: Blob
}

/** Every capture this device still holds bytes for, for one run. */
export async function listCaptureBlobs(runId: number): Promise<StoredCapture[]> {
  const db = await getDb()
  if (!db) return []
  const scope = currentLedgerNamespace()
  if (!scope) return []
  try {
    const prefix = `${runPrefix(scope, runId)}${KEY_SEP}`
    const records = await db.getAll(BLOB_STORE)
    return records
      .filter((record) => record.key.startsWith(prefix))
      .map((record) => ({
        captureId: record.captureId,
        questionId: record.questionId,
        kind: record.kind,
        blob: record.blob,
      }))
  } catch {
    return []
  }
}

export async function deleteCaptureBlob(runId: number, captureId: string): Promise<void> {
  const db = await getDb()
  if (!db) return
  const scope = currentLedgerNamespace()
  if (!scope) return
  try {
    await db.delete(BLOB_STORE, blobKey(scope, runId, captureId))
  } catch {
    /* best effort — a leftover blob costs quota, not correctness */
  }
}

// ---------------------------------------------------------------------------
// Purge
// ---------------------------------------------------------------------------

/**
 * Prefix delete over primary keys.
 *
 * `getAllKeys` rather than a cursor over `IDBKeyRange`: the ledger is one
 * auditor's in-flight work, so the key list is tens of entries, and reading keys
 * never deserialises a blob.
 */
async function deleteBlobsWithPrefix(
  db: IDBPDatabase<AuditLedgerSchema>,
  prefix: string,
): Promise<void> {
  const keys = await db.getAllKeys(BLOB_STORE)
  await Promise.all(
    keys.filter((key) => String(key).startsWith(prefix)).map((key) => db.delete(BLOB_STORE, key)),
  )
}

async function deleteLedgerWithPrefix(
  db: IDBPDatabase<AuditLedgerSchema>,
  prefix: string,
): Promise<void> {
  const keys = await db.getAllKeys(LEDGER_STORE)
  await Promise.all(
    keys.filter((key) => String(key).startsWith(prefix)).map((key) => db.delete(LEDGER_STORE, key)),
  )
}

/**
 * Remove everything one namespace owns — answers and bytes.
 *
 * Called by the deliberate sign-out handlers only. The auth-loss path in
 * `api/client.ts` must NOT call this: it has just flushed the auditor's unsaved
 * answers here on purpose, and a session that timed out is not a handover.
 */
export async function purgeDeviceLedger(namespace: string): Promise<void> {
  const db = await getDb()
  if (!db) return
  try {
    const prefix = `${namespace}${KEY_SEP}`
    await deleteLedgerWithPrefix(db, prefix)
    await deleteBlobsWithPrefix(db, prefix)
  } catch {
    /* nothing to escalate: sign-out must complete either way */
  }
}

/**
 * Purge the signed-in auditor's namespace, then forget the namespace itself.
 *
 * Must be awaited *before* `clearAuthState()`: the namespace is derived from the
 * access token's `sub`, so once the token is gone there is no way to work out
 * which rows were theirs.
 */
export async function purgeDeviceLedgerForCurrentSession(): Promise<void> {
  const namespace = currentLedgerNamespace()
  if (namespace) {
    await purgeDeviceLedger(namespace)
  }
  clearDeviceLedgerIdentity()
}

// ---------------------------------------------------------------------------
// In-memory snapshot registry
// ---------------------------------------------------------------------------
// AuditExecution registers a snapshot function on mount; api/client.ts calls
// every registered snapshot just before any auth-loss redirect so unsaved
// answers get stashed before the page navigates away. This keeps the audit page
// decoupled from the auth client (it never has to know about clearTokens).

type DraftSnapshot = () => AuditDraft | null
const snapshotProviders = new Map<number, DraftSnapshot>()

export function registerDraftSnapshot(runId: number, provider: DraftSnapshot): () => void {
  snapshotProviders.set(runId, provider)
  return () => {
    if (snapshotProviders.get(runId) === provider) {
      snapshotProviders.delete(runId)
    }
  }
}

/**
 * Synchronously collect every registered draft snapshot, then asynchronously
 * write them.
 *
 * The namespace is resolved **synchronously, here**, and passed down. The caller
 * (`clearAndRedirectToLogin`) clears the access token in the same tick, and the
 * namespace is derived from that token — resolving it inside the async write
 * would attribute the flush to nobody and drop it on the floor.
 */
export function flushAllDraftsToIndexedDb(
  reason: AuditDraft['reason'] = 'auth-loss',
): Promise<void> {
  const namespace = currentLedgerNamespace()
  const drafts: AuditDraft[] = []
  for (const provider of snapshotProviders.values()) {
    try {
      const snap = provider()
      if (snap && Object.keys(snap.responses).length > 0) {
        drafts.push({ ...snap, reason, savedAt: Date.now() })
      }
    } catch {
      /* one bad provider mustn't stop the others */
    }
  }
  if (drafts.length === 0) return Promise.resolve()
  if (!namespace) {
    // Nothing can be attributed, so nothing is written. Reported rather than
    // silently dropped, so the login screen is not the first hint.
    reportFailure('no-identity')
    return Promise.resolve()
  }
  return Promise.all(drafts.map((draft) => saveAuditDraft(draft, namespace))).then(() => undefined)
}
