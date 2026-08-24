/**
 * WJ-1 native draft editor shell (L-35).
 *
 * Draft-only block JSON — no HTML store, no CRDT, no Office round-trip. The
 * shell renders the blocks a native document already holds and exposes the two
 * seams the authoring path needs: a single-writer lease (L-38) and a draft save.
 *
 * Neither seam has a backend in M1. Rather than render a button that would throw
 * on click, the shell disables the control and says which endpoint is missing —
 * an author who cannot save needs to know that before they type, not after.
 */
import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import type { DraftLeaseStub, NativeDraftDocument } from './types'

export const LIBRARY_EDITOR_CHUNK_ID = 'library-native-draft-editor' as const

export const EMPTY_NATIVE_DRAFT: NativeDraftDocument = {
  schemaVersion: 1,
  blocks: [],
}

export interface NativeDraftEditorShellProps {
  documentId: number
  draft?: NativeDraftDocument
  /** L-38 single-writer lease. `null` means no lease is held or none is served. */
  lease?: DraftLeaseStub | null
  /**
   * Persist the draft. Omitted while no endpoint exists — the shell then shows a
   * disabled control naming the gap instead of pretending to save.
   */
  onSaveDraft?: (draft: NativeDraftDocument) => Promise<void> | void
  /** Take the single-writer lease. Omitted while no lease endpoint exists. */
  onAcquireLease?: () => Promise<void> | void
  /** Where version publish actually lives (L-37 stays on the publish path). */
  publishHref?: string | null
}

export function NativeDraftEditorShell({
  documentId,
  draft = EMPTY_NATIVE_DRAFT,
  lease = null,
  onSaveDraft,
  onAcquireLease,
  publishHref = null,
}: NativeDraftEditorShellProps) {
  const blockCount = draft.blocks.length
  const canSave = typeof onSaveDraft === 'function'
  const canAcquireLease = typeof onAcquireLease === 'function'
  const leaseLabel = lease?.holderUserId
    ? `Draft lease held by user ${lease.holderUserId}${lease.expiresAt ? ` until ${lease.expiresAt}` : ''}`
    : 'No draft lease held'

  return (
    <section
      className="rounded-md border border-border/70 bg-surface p-4"
      data-testid="library-native-draft-editor-shell"
      data-document-id={String(documentId)}
      data-chunk-id={LIBRARY_EDITOR_CHUNK_ID}
      aria-label="Native draft editor"
    >
      <header className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-foreground">Native draft</h2>
        <p className="text-xs text-muted-foreground" data-testid="library-editor-lease-state">
          {leaseLabel}
        </p>
      </header>

      <p className="text-sm text-muted-foreground" data-testid="library-editor-block-count">
        {blockCount} block{blockCount === 1 ? '' : 's'} (restricted JSON schema v
        {draft.schemaVersion})
      </p>

      {blockCount > 0 ? (
        <ol className="mt-3 space-y-2" data-testid="library-editor-blocks">
          {draft.blocks.map((block) => (
            <li
              key={block.id}
              className="rounded border border-border/60 p-2 text-sm text-foreground"
              data-block-type={block.type}
            >
              {block.text}
            </li>
          ))}
        </ol>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={!canSave}
          onClick={canSave ? () => void onSaveDraft?.(draft) : undefined}
          data-testid="library-editor-save-draft"
        >
          Save draft
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!canAcquireLease}
          onClick={canAcquireLease ? () => void onAcquireLease?.() : undefined}
          data-testid="library-editor-acquire-lease"
        >
          Take draft lease
        </Button>
        {publishHref ? (
          <Button size="sm" variant="ghost" asChild>
            <Link to={publishHref} data-testid="library-editor-publish-link">
              Publish from History
            </Link>
          </Button>
        ) : null}
      </div>

      {!canSave || !canAcquireLease ? (
        <p className="mt-2 text-xs text-muted-foreground" data-testid="library-editor-backend-gap">
          Authoring is read-only in this release. QGP serves no draft-content or
          draft-lease endpoint yet, so nothing typed here could be persisted or protected
          from a second writer. Publishing an existing version is unaffected and stays on
          the History layer.
        </p>
      ) : null}
    </section>
  )
}

export default NativeDraftEditorShell
