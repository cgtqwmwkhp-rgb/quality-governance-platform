/**
 * WJ-1 Front Sheet band (L-36).
 *
 * Binary documents are never edited in-app, so the band is a live cover composed
 * from the Register row rather than a page of the file. It reads; it never
 * writes, and it never touches the stored bytes.
 *
 * Missing values are shown as missing. On a governance cover sheet a plausible
 * blank is worse than an obvious hole — a reader who cannot tell the difference
 * between "no review date" and "review date not recorded" cannot act on either.
 */
import { Badge } from '../components/ui/Badge'
import { formatLibraryDate } from './formatLibraryDate'
import type { FrontSheetBandModel } from './types'

export interface FrontSheetBandProps {
  model: FrontSheetBandModel
  /** Why this document took the Front Sheet path rather than the draft editor. */
  formatNote?: string | null
}

const NOT_RECORDED = 'Not recorded'

function Field({
  label,
  value,
  testId,
}: {
  label: string
  value: string | null
  testId: string
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground" data-testid={testId}>
        {value ?? NOT_RECORDED}
      </dd>
    </div>
  )
}

export function FrontSheetBand({ model, formatNote = null }: FrontSheetBandProps) {
  const { retention } = model

  return (
    <section
      className="rounded-md border border-border bg-surface/80 p-4"
      data-testid="library-front-sheet-band"
      data-document-id={String(model.documentId)}
      aria-label="Document front sheet"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Front Sheet
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {model.statusLabel ? (
            <Badge variant="secondary" data-testid="front-sheet-status">
              {model.statusLabel}
            </Badge>
          ) : null}
          {model.controlStatusLabel ? (
            <Badge variant="outline" data-testid="front-sheet-control-status">
              Control: {model.controlStatusLabel}
            </Badge>
          ) : null}
          {model.isStatutory ? (
            <Badge variant="warning" data-testid="front-sheet-statutory">
              Statutory
            </Badge>
          ) : null}
          {model.legalHoldActive ? (
            <Badge variant="destructive" data-testid="front-sheet-legal-hold">
              Legal hold
              {model.legalMatterReference ? ` · ${model.legalMatterReference}` : ''}
            </Badge>
          ) : null}
        </div>
      </div>

      <h2 className="mt-1 text-base font-semibold text-foreground">
        {model.title || 'Untitled document'}
      </h2>
      <p className="font-mono text-sm text-primary" data-testid="front-sheet-lead-reference">
        {model.leadReference}
        {model.secondaryReference ? (
          <span className="ml-2 font-sans text-xs text-muted-foreground">
            {model.secondaryReference}
          </span>
        ) : null}
      </p>

      <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Issue" value={model.issueLabel} testId="front-sheet-issue" />
        <Field label="Function" value={model.functionCode} testId="front-sheet-function" />
        <Field
          label="Cascade level"
          value={model.cascadeLevel === null ? null : String(model.cascadeLevel)}
          testId="front-sheet-cascade-level"
        />
        <Field label="Access" value={model.accessLevel} testId="front-sheet-access" />
        <Field
          label="Effective"
          value={formatLibraryDate(model.effectiveDate)}
          testId="front-sheet-effective"
        />
        <Field
          label="Next review"
          value={formatLibraryDate(model.reviewDate)}
          testId="front-sheet-review"
        />
      </dl>

      <div
        className="mt-3 rounded-md border border-border/70 bg-background/60 p-3"
        data-testid="front-sheet-retention"
        data-policy-resolved={String(retention.policyResolved)}
      >
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Retention (R19)</p>
        <p className="text-sm font-medium text-foreground" data-testid="front-sheet-retention-headline">
          {retention.headline}
        </p>
        <p className="mt-1 text-sm text-muted-foreground" data-testid="front-sheet-retention-detail">
          {retention.detail}
        </p>
        {retention.basis ? (
          <p className="mt-1 text-xs text-muted-foreground" data-testid="front-sheet-retention-basis">
            Basis: {retention.basis}
          </p>
        ) : null}
      </div>

      <p className="mt-3 text-sm text-muted-foreground" data-testid="front-sheet-coverage">
        Coverage: {model.coverageSummary ?? 'not composed — evidence-pack coverage is not built yet'}
      </p>

      <p className="mt-2 text-xs text-muted-foreground" data-testid="front-sheet-format-note">
        {formatNote ??
          'Stored bytes are never modified from this band. Revise by replacing the file from the History layer.'}
        {model.fileName ? ` Current file: ${model.fileName}.` : ''}
      </p>
    </section>
  )
}

export default FrontSheetBand
