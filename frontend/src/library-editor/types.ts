/**
 * WJ-1 native draft editor + Front Sheet — shared types.
 *
 * This package is mounted into DocumentDetail only through a dynamic import, so
 * nothing here may be referenced from the App shell. See
 * `docs/governance/library-wj1-size-limit-notes.md`.
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

/** L-38 — single-writer lease; no CRDT. No endpoint serves this yet. */
export interface DraftLeaseStub {
  documentId: number
  holderUserId: number | null
  acquiredAt: string | null
  expiresAt: string | null
}

/**
 * The subset of `DocumentResponse` the Detail body reads.
 *
 * Declared structurally rather than imported from the page: DocumentDetail must
 * not take a value dependency on this package, or the editor rejoins the route
 * chunk. Every field is optional except the two the band cannot render without,
 * because a legacy row can be missing any of them.
 */
export interface LibraryBodyDocument {
  id: number
  title: string
  reference_number?: string | null
  pel_doc_ref?: string | null
  cascade_level?: number | null
  document_type?: string | null
  category?: string | null
  department?: string | null
  status?: string | null
  version?: string | null
  file_name?: string | null
  file_type?: string | null
  access_level?: string | null
  is_statutory?: boolean | null
  controlled_document_id?: number | null
  control_status?: string | null
  legal_matter_reference?: string | null
  legal_hold_active?: boolean | null
  effective_date?: string | null
  review_date?: string | null
  /** CUT-1 / R19 — the policy the disposal date was calculated from. */
  retention_until?: string | null
  retention_years?: number | null
  retention_anchor?: string | null
  retention_basis?: string | null
  /**
   * L-34. Not served by `DocumentResponse` yet — the column and its alembic
   * revision are WJ-1-M2. Read optionally so the native path activates the day
   * the API starts answering, without a second FE release.
   */
  content_format?: string | null
}

/** CUT-1 retention, rendered for a human rather than as four raw columns. */
export interface RetentionDisplay {
  /** The policy in one line, or the honest absence of one. */
  headline: string
  /** Why this document does or does not have a disposal date. */
  detail: string
  /** Formatted `retention_until` when the row carries one. */
  disposalDate: string | null
  /** R19 basis — the governance prose the number was read from, verbatim. */
  basis: string | null
  /** True when years and a recognised anchor are both present on the row. */
  policyResolved: boolean
}

/** Props the Front Sheet band binds from the Register row (L-36). */
export interface FrontSheetBandModel {
  documentId: number
  title: string
  /** Auditor-facing lead reference — PEL when allocated, else DOC. */
  leadReference: string
  secondaryReference: string | null
  issueLabel: string | null
  statusLabel: string | null
  controlStatusLabel: string | null
  functionCode: string | null
  cascadeLevel: number | null
  accessLevel: string | null
  isStatutory: boolean
  legalHoldActive: boolean
  legalMatterReference: string | null
  fileName: string | null
  effectiveDate: string | null
  reviewDate: string | null
  retention: RetentionDisplay
  /** Coverage chips are composed by CEL / evidence packs — no source yet. */
  coverageSummary: string | null
}
