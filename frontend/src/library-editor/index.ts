/**
 * WJ-1 library editor package shell.
 *
 * Import via dynamic `import('../library-editor')` (or this barrel) so Vite emits
 * a separate chunk. Do not static-import from App shell or DocumentDetail until
 * WJ-0 is LIVE and size-limit notes in docs/governance are applied.
 *
 * @see docs/adr/ADR-0024-native-draft-editor-and-front-sheet.md
 * @see docs/governance/library-wj1-size-limit-notes.md
 */

export { FrontSheetBand } from './FrontSheetBand'
export type { FrontSheetBandProps } from './FrontSheetBand'
export {
  EMPTY_NATIVE_DRAFT,
  LIBRARY_EDITOR_CHUNK_ID,
  NativeDraftEditorShell,
} from './NativeDraftEditorShell'
export type { NativeDraftEditorShellProps } from './NativeDraftEditorShell'
export type {
  DraftLeaseStub,
  FrontSheetBandModel,
  LibraryContentFormat,
  NativeDraftBlock,
  NativeDraftBlockType,
  NativeDraftDocument,
} from './types'

/** Stable marker for tests + future size-limit path notes. */
export const LIBRARY_EDITOR_PACKAGE = 'frontend/src/library-editor' as const
