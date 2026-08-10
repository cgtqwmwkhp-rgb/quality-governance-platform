/**
 * WJ-1 native draft editor shell (scaffold).
 *
 * Lazy-chunk entry for L-35. Not mounted from DocumentDetail yet — WB-1 owns
 * Detail layers; WJ-1 takes Detail body only after WJ-0 PROD.
 */
import type { DraftLeaseStub, NativeDraftDocument } from './types'

export const LIBRARY_EDITOR_CHUNK_ID = 'library-native-draft-editor' as const

export const EMPTY_NATIVE_DRAFT: NativeDraftDocument = {
  schemaVersion: 1,
  blocks: [],
}

export interface NativeDraftEditorShellProps {
  documentId: number
  draft?: NativeDraftDocument
  lease?: DraftLeaseStub | null
  /** When false, shell renders honesty that authoring waits on WJ-0. */
  authoringEnabled?: boolean
  readOnly?: boolean
}

/**
 * Presentational shell only — no persistence, lease API, or publish path.
 */
export function NativeDraftEditorShell({
  documentId,
  draft = EMPTY_NATIVE_DRAFT,
  lease = null,
  authoringEnabled = false,
  readOnly = true,
}: NativeDraftEditorShellProps) {
  const blockCount = draft.blocks.length
  const leaseLabel = lease?.holderUserId
    ? `Lease held by user ${lease.holderUserId}`
    : 'No draft lease'

  return (
    <section
      className="rounded-md border border-border/70 bg-surface p-3"
      data-testid="library-native-draft-editor-shell"
      data-document-id={String(documentId)}
      data-chunk-id={LIBRARY_EDITOR_CHUNK_ID}
      aria-label="Native draft editor scaffold"
    >
      <header className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-foreground">Native draft editor</h2>
        <p className="text-xs text-muted-foreground" data-testid="library-editor-lease-stub">
          {leaseLabel}
        </p>
      </header>

      {!authoringEnabled ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="library-editor-waiting-wj0"
        >
          Authoring is scaffolded only. Mount after WJ-0 drops collaborative_* and
          Detail wiring lands in WJ-1 (L-35 / L-38). No CRDT, no Office round-trip.
        </p>
      ) : (
        <p className="text-sm text-muted-foreground" data-testid="library-editor-block-count">
          {readOnly ? 'Read-only draft' : 'Editable draft'} · {blockCount} block
          {blockCount === 1 ? '' : 's'} (restricted JSON schema v{draft.schemaVersion})
        </p>
      )}
    </section>
  )
}

export default NativeDraftEditorShell
