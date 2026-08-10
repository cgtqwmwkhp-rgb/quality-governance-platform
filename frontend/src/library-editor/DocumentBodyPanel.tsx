/**
 * WJ-1-M1 — the Document Detail body, loaded as its own chunk.
 *
 * This is the only module DocumentDetail imports from `library-editor`, and it
 * imports it dynamically. Everything the body needs hangs off here so the editor
 * package never rejoins the route chunk or the App shell
 * (`docs/governance/library-wj1-size-limit-notes.md`).
 *
 * One decision lives here: which body a document gets (L-34). Binary documents
 * get the Front Sheet cover; native documents get the draft editor. Nothing in
 * this panel writes.
 */
import { documentLayerHref } from '../pages/documentEvidenceTab'
import { describeContentFormatReason, resolveLibraryContentFormat } from './contentFormat'
import { FrontSheetBand } from './FrontSheetBand'
import { buildFrontSheetBandModel } from './frontSheetModel'
import { NativeDraftEditorShell } from './NativeDraftEditorShell'
import type { LibraryBodyDocument } from './types'

export interface DocumentBodyPanelProps {
  document: LibraryBodyDocument
}

export function DocumentBodyPanel({ document }: DocumentBodyPanelProps) {
  const decision = resolveLibraryContentFormat(document)
  const formatNote = describeContentFormatReason(decision)

  return (
    <div
      data-testid="library-document-body"
      data-content-format={decision.format}
      data-content-format-reason={decision.reason}
    >
      {decision.format === 'native' ? (
        <NativeDraftEditorShell
          documentId={document.id}
          publishHref={documentLayerHref(document.id, 'history')}
        />
      ) : (
        <FrontSheetBand model={buildFrontSheetBandModel(document)} formatNote={formatNote} />
      )}
    </div>
  )
}

export default DocumentBodyPanel
