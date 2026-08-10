/**
 * WJ-1 library editor package.
 *
 * Mounted only through the dynamic import in `DocumentDetail.tsx`, which loads
 * `DocumentBodyPanel` directly. This barrel exists for tests and for callers that
 * want the whole package; importing it from the App shell would put the editor
 * back on the index chunk.
 *
 * @see docs/adr/ADR-0024-native-draft-editor-and-front-sheet.md
 * @see docs/governance/library-wj1-size-limit-notes.md
 */

export { describeContentFormatReason, resolveLibraryContentFormat } from './contentFormat'
export type { ContentFormatDecision, ContentFormatReason } from './contentFormat'
export { DocumentBodyPanel } from './DocumentBodyPanel'
export type { DocumentBodyPanelProps } from './DocumentBodyPanel'
export { FrontSheetBand } from './FrontSheetBand'
export type { FrontSheetBandProps } from './FrontSheetBand'
export { buildFrontSheetBandModel, libraryFunctionCode } from './frontSheetModel'
export {
  EMPTY_NATIVE_DRAFT,
  LIBRARY_EDITOR_CHUNK_ID,
  NativeDraftEditorShell,
} from './NativeDraftEditorShell'
export type { NativeDraftEditorShellProps } from './NativeDraftEditorShell'
export { formatLibraryDate } from './formatLibraryDate'
export { describeLibraryRetention } from './retentionDisplay'
export type { LibraryRetentionAnchor } from './retentionDisplay'
export type {
  DraftLeaseStub,
  FrontSheetBandModel,
  LibraryBodyDocument,
  LibraryContentFormat,
  NativeDraftBlock,
  NativeDraftBlockType,
  NativeDraftDocument,
  RetentionDisplay,
} from './types'

/** Stable marker for tests + size-limit path notes. */
export const LIBRARY_EDITOR_PACKAGE = 'frontend/src/library-editor' as const
