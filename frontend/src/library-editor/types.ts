/**
 * WJ-1 native draft editor + Front Sheet — shared types (scaffold).
 *
 * Wire into DocumentDetail / publish only after WJ-0 PROD (collaborative_* dropped).
 * Do not import this module from the shell index route yet — keep size-limit green.
 */

/** L-34 — legacy uploads are binary; native is an explicit conversion act. */
export type LibraryContentFormat = 'binary' | 'native'

/** Restricted block JSON — never HTML store (L-35). */
export type NativeDraftBlockType = 'paragraph' | 'heading' | 'list' | 'callout'

export interface NativeDraftBlock {
  id: string
  type: NativeDraftBlockType
  text: string
  level?: 1 | 2 | 3
}

export interface NativeDraftDocument {
  schemaVersion: 1
  blocks: NativeDraftBlock[]
}

/** L-38 — single-writer lease; no CRDT. */
export interface DraftLeaseStub {
  documentId: number
  holderUserId: number | null
  acquiredAt: string | null
  expiresAt: string | null
}

/** Props the Front Sheet band will eventually bind from control + coverage. */
export interface FrontSheetBandModel {
  documentId: number
  title: string
  pelReference: string | null
  issueLabel: string | null
  statusLabel: string | null
  functionCode: string | null
  /** Coverage chips are composed later (CEL / packs) — stub only. */
  coverageSummary: string | null
}
