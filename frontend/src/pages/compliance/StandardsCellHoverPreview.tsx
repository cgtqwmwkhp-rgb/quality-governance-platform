import { useTranslation } from 'react-i18next'
import { Badge } from '../../components/ui'
import { cn } from '../../helpers/utils'

export type CellVerdictStub = 'covered' | 'partial' | 'gap' | 'unknown'

export interface StandardsCellHoverPreviewProps {
  frameworkLabel: string
  clauseNumber: string
  clauseTitle: string
  verdict: CellVerdictStub
  /** Top evidence title — stub until PR-B live graph */
  topEvidenceLabel?: string | null
  /** Freshness label — stub until PR-B live graph */
  freshnessLabel?: string | null
  className?: string
}

const verdictTone: Record<CellVerdictStub, string> = {
  covered: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  partial: 'bg-amber-500/15 text-amber-800 dark:text-amber-300',
  gap: 'bg-destructive/15 text-destructive',
  unknown: 'bg-muted text-muted-foreground',
}

/**
 * Enhancement #2 — hover preview chrome (verdict · top evidence · freshness).
 * Values are honest stubs until PR-B wires the live graph.
 */
export function StandardsCellHoverPreview({
  frameworkLabel,
  clauseNumber,
  clauseTitle,
  verdict,
  topEvidenceLabel,
  freshnessLabel,
  className,
}: StandardsCellHoverPreviewProps) {
  const { t } = useTranslation()

  return (
    <div
      className={cn('space-y-2 max-w-xs text-left', className)}
      data-testid="standards-cell-hover-preview"
    >
      <div className="text-xs font-medium text-muted-foreground">{frameworkLabel}</div>
      <div className="text-sm font-semibold text-foreground">
        {clauseNumber}
        <span className="font-normal text-muted-foreground"> · {clauseTitle}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="secondary"
          className={cn('text-xs', verdictTone[verdict])}
          data-testid="standards-cell-hover-verdict"
        >
          {t(`compliance.standards_matrix.verdict.${verdict}`, {
            defaultValue: verdict,
          })}
        </Badge>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {t('compliance.standards_matrix.stub_badge', { defaultValue: 'PR-B stub' })}
        </span>
      </div>
      <dl className="grid gap-1 text-xs text-muted-foreground">
        <div className="flex justify-between gap-3">
          <dt>{t('compliance.standards_matrix.hover.top_evidence', { defaultValue: 'Top evidence' })}</dt>
          <dd className="text-foreground text-right">
            {topEvidenceLabel ??
              t('compliance.standards_matrix.hover.top_evidence_stub', {
                defaultValue: 'Live graph in PR-B',
              })}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>{t('compliance.standards_matrix.hover.freshness', { defaultValue: 'Freshness' })}</dt>
          <dd className="text-foreground text-right">
            {freshnessLabel ??
              t('compliance.standards_matrix.hover.freshness_stub', {
                defaultValue: 'Not wired yet',
              })}
          </dd>
        </div>
      </dl>
    </div>
  )
}
