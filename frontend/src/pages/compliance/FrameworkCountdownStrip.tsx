import { useTranslation } from 'react-i18next'
import { Badge, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui'
import { cn } from '../../helpers/utils'
import type { FrameworkCountdown, FrameworkCountdownEntry } from '../../api/standardsCellAggregateTypes'
import type { FrameworkDef } from './standardsMatrixFilters'

export function countdownChipLabel(entry: FrameworkCountdownEntry | undefined): {
  status: string
  days: number | null
} {
  if (!entry || entry.status === 'none' || entry.days_remaining == null) {
    return { status: 'none', days: null }
  }
  return { status: String(entry.status), days: entry.days_remaining }
}

function chipTone(status: string): string {
  switch (status) {
    case 'expired':
      return 'border-destructive/40 text-destructive'
    case 'due_soon':
      return 'border-amber-500/40 text-amber-600 dark:text-amber-400'
    case 'current':
      return 'border-border text-muted-foreground'
    default:
      return 'border-border text-muted-foreground'
  }
}

export function FrameworkCountdownStrip({
  columns,
  countdown,
}: {
  columns: FrameworkDef[]
  countdown: FrameworkCountdown
}) {
  const { t } = useTranslation()

  return (
    <div className="space-y-2" data-testid="standards-matrix-countdown">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {t('compliance.standards_matrix.countdown.title', { defaultValue: 'Certificate countdown' })}
        </span>
        <TooltipProvider delayDuration={200}>
          {columns.map((col) => {
            const entry = countdown.frameworks[col.id]
            const chip = countdownChipLabel(entry)
            const label =
              chip.status === 'none' || chip.days == null
                ? t('compliance.standards_matrix.countdown.none', { defaultValue: 'No dated cert' })
                : chip.status === 'expired'
                  ? t('compliance.standards_matrix.countdown.expired', {
                      defaultValue: 'Expired {{days}}d',
                      days: Math.abs(chip.days),
                    })
                  : t('compliance.standards_matrix.countdown.days', {
                      defaultValue: '{{days}}d',
                      days: chip.days,
                    })
            return (
              <Tooltip key={col.id}>
                <TooltipTrigger asChild>
                  <Badge
                    variant="outline"
                    className={cn('text-[10px]', chipTone(chip.status))}
                    data-testid={`standards-matrix-countdown-${col.id}`}
                    data-status={chip.status}
                  >
                    {col.shortLabel} · {label}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                  {entry?.name && entry.next_expiry
                    ? `${entry.name} · ${entry.next_expiry}`
                    : t('compliance.standards_matrix.countdown.none_hint', {
                        defaultValue: 'No attributed dated certificate for this column',
                      })}
                </TooltipContent>
              </Tooltip>
            )
          })}
        </TooltipProvider>
      </div>
      {countdown.unmatched_on_shelf ? (
        <p className="text-[11px] text-muted-foreground" data-testid="standards-matrix-countdown-unmatched">
          {t('compliance.standards_matrix.countdown.unmatched', {
            defaultValue:
              'Shelf also has items that are not framework proof (PAT, insurance, training) — they do not set these days.',
          })}
        </p>
      ) : null}
    </div>
  )
}
