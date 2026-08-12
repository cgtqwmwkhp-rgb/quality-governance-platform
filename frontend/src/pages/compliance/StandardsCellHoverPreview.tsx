import { useTranslation } from 'react-i18next'
import { Badge } from '../../components/ui'
import { cn } from '../../helpers/utils'
import type { CellVerdict } from '../../api/standardsCellAggregateTypes'

export type CellVerdictStub = CellVerdict

export interface StandardsCellHoverPreviewProps {
  frameworkLabel: string
  /** Official home page for the framework; renders the label as a link when set. */
  frameworkHomeUrl?: string | null
  clauseNumber: string
  clauseTitle: string
  verdict: CellVerdictStub
  /** Top evidence title from live aggregate */
  topEvidenceLabel?: string | null
  /** Freshness label from live aggregate */
  freshnessLabel?: string | null
  coverBlocked?: boolean
  recurrenceRedFlag?: boolean
  /** When false, hide the PR-B stub chrome (live data wired). */
  isStub?: boolean
  /** PR-C: imported 5064 row verdict (EXACT / NEAR / DIFFERENT / UNIQUE). */
  alignmentVerdict?: string | null
  /** PR-C: this clause number is shared with a materially different requirement. */
  isTrapRow?: boolean
  /** PR-C: technical control with no attestation source — cannot be covered by a PDF. */
  techGapStub?: boolean
  className?: string
}

const verdictTone: Record<CellVerdictStub, string> = {
  covered: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  partial: 'bg-amber-500/15 text-amber-800 dark:text-amber-300',
  gap: 'bg-destructive/15 text-destructive',
  unknown: 'bg-muted text-muted-foreground',
}

/**
 * Enhancement #2 — hover preview (verdict · top evidence · freshness).
 * PR-B wires live aggregate values; stub mode remains for offline/fallback.
 */
export function StandardsCellHoverPreview({
  frameworkLabel,
  frameworkHomeUrl = null,
  clauseNumber,
  clauseTitle,
  verdict,
  topEvidenceLabel,
  freshnessLabel,
  coverBlocked = false,
  recurrenceRedFlag = false,
  isStub = false,
  alignmentVerdict = null,
  isTrapRow = false,
  techGapStub = false,
  className,
}: StandardsCellHoverPreviewProps) {
  const { t } = useTranslation()

  return (
    <div
      className={cn('space-y-2 max-w-xs text-left', className)}
      data-testid="standards-cell-hover-preview"
    >
      <div className="text-xs font-medium text-muted-foreground">
        {frameworkHomeUrl ? (
          <a
            href={frameworkHomeUrl}
            target="_blank"
            rel="noreferrer noopener"
            className="underline-offset-2 hover:underline"
            data-testid="standards-cell-hover-framework-link"
          >
            {frameworkLabel}
          </a>
        ) : (
          frameworkLabel
        )}
      </div>
      <div className="text-sm font-semibold text-foreground">
        {clauseNumber}
        <span className="font-normal text-muted-foreground"> · {clauseTitle}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="secondary"
          className={cn('text-xs', verdictTone[verdict] ?? verdictTone.unknown)}
          data-testid="standards-cell-hover-verdict"
        >
          {t(`compliance.standards_matrix.verdict.${verdict}`, {
            defaultValue: verdict,
          })}
        </Badge>
        {coverBlocked ? (
          <Badge variant="destructive" className="text-xs" data-testid="standards-cell-hover-cover-blocked">
            {t('compliance.standards_workspace.cover_blocked_badge', { defaultValue: 'Cover blocked' })}
          </Badge>
        ) : null}
        {recurrenceRedFlag ? (
          <Badge variant="destructive" className="text-xs" data-testid="standards-cell-hover-recurrence">
            {t('compliance.standards_workspace.recurrence_badge', { defaultValue: 'Recurrence' })}
          </Badge>
        ) : null}
        {alignmentVerdict ? (
          <Badge variant="outline" className="text-xs" data-testid="standards-cell-hover-alignment">
            {alignmentVerdict}
          </Badge>
        ) : null}
        {isTrapRow ? (
          <Badge variant="destructive" className="text-xs" data-testid="standards-cell-hover-trap">
            {t('compliance.standards_matrix.trap_badge', { defaultValue: 'Trap row' })}
          </Badge>
        ) : null}
        {techGapStub ? (
          <Badge variant="destructive" className="text-xs" data-testid="standards-cell-hover-tech-gap">
            {t('compliance.standards_matrix.tech_gap_badge', {
              defaultValue: 'Needs technical proof',
            })}
          </Badge>
        ) : null}
        {isStub ? (
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {t('compliance.standards_matrix.stub_badge', { defaultValue: 'PR-B stub' })}
          </span>
        ) : (
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {t('compliance.standards_matrix.live_badge', { defaultValue: 'Live graph' })}
          </span>
        )}
      </div>
      <dl className="grid gap-1 text-xs text-muted-foreground">
        <div className="flex justify-between gap-3">
          <dt>{t('compliance.standards_matrix.hover.top_evidence', { defaultValue: 'Top evidence' })}</dt>
          <dd className="text-foreground text-right">
            {topEvidenceLabel ??
              t('compliance.standards_matrix.hover.top_evidence_none', {
                defaultValue: 'None linked',
              })}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>{t('compliance.standards_matrix.hover.freshness', { defaultValue: 'Freshness' })}</dt>
          <dd className="text-foreground text-right">
            {freshnessLabel ??
              t('compliance.standards_matrix.hover.freshness_none', {
                defaultValue: 'No activity',
              })}
          </dd>
        </div>
      </dl>
    </div>
  )
}
