/**
 * WJ-1 Front Sheet band stub (L-36).
 *
 * Binary documents are never edited in-app — this band is a live cover from
 * control + coverage. Bytes stay untouched; replacement-on-revise is the mutate path.
 * Do not mount from DocumentDetail until WJ-0 PROD + WJ-1 Detail ownership.
 */
import type { FrontSheetBandModel } from './types'

export interface FrontSheetBandProps {
  model: FrontSheetBandModel
  /** Scaffold default: honesty that coverage composition waits on WI/CEL layers. */
  showScaffoldHonesty?: boolean
}

export function FrontSheetBand({
  model,
  showScaffoldHonesty = true,
}: FrontSheetBandProps) {
  const {
    title,
    pelReference,
    issueLabel,
    statusLabel,
    functionCode,
    coverageSummary,
    documentId,
  } = model

  return (
    <aside
      className="rounded-md border border-border bg-surface/80 p-3"
      data-testid="library-front-sheet-band"
      data-document-id={String(documentId)}
      aria-label="Document front sheet"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Front Sheet
      </p>
      <h2 className="mt-1 text-base font-semibold text-foreground">{title || 'Untitled document'}</h2>

      <dl className="mt-2 grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">PEL</dt>
          <dd data-testid="front-sheet-pel">{pelReference ?? 'Not allocated'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Issue</dt>
          <dd data-testid="front-sheet-issue">{issueLabel ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Status</dt>
          <dd data-testid="front-sheet-status">{statusLabel ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Function</dt>
          <dd data-testid="front-sheet-function">{functionCode ?? '—'}</dd>
        </div>
      </dl>

      <p className="mt-2 text-sm text-muted-foreground" data-testid="front-sheet-coverage">
        Coverage: {coverageSummary ?? 'Not composed yet'}
      </p>

      {showScaffoldHonesty ? (
        <p className="mt-2 text-xs text-muted-foreground" data-testid="front-sheet-scaffold-note">
          Scaffold only (L-36). Binary bytes are never mutated here. Bind control +
          CEL coverage after WJ-0 PROD; render-on-publish (L-37) stays on the publish path.
        </p>
      ) : null}
    </aside>
  )
}

export default FrontSheetBand
