import { CheckCircle2, Circle, CircleDashed } from 'lucide-react'
import { cn } from '../../helpers/utils'
import type { ContractSectionCheckItem } from './contractSections'
import { INC043_CONTRACT_SECTIONS } from './contractSections'

interface ContractSectionChecklistProps {
  checklist: ContractSectionCheckItem[]
  compact?: boolean
  className?: string
}

function statusIcon(status: ContractSectionCheckItem['status']) {
  if (status === 'complete') {
    return <CheckCircle2 size={16} className="text-success shrink-0" aria-hidden="true" />
  }
  if (status === 'partial') {
    return <CircleDashed size={16} className="text-warning shrink-0" aria-hidden="true" />
  }
  return <Circle size={16} className="text-muted-foreground shrink-0" aria-hidden="true" />
}

function statusLabel(status: ContractSectionCheckItem['status']) {
  if (status === 'complete') {
    return 'Has questions'
  }
  if (status === 'partial') {
    return 'Section present — add questions'
  }
  return 'Missing section'
}

export function ContractSectionChecklist({
  checklist,
  compact = false,
  className,
}: ContractSectionChecklistProps) {
  const presentCount = checklist.filter((item) => item.status !== 'missing').length
  const completeCount = checklist.filter((item) => item.status === 'complete').length

  return (
    <div className={cn('space-y-3', className)} data-testid="inc043-section-checklist">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-foreground">INC043 section contract</p>
          <p className="text-xs text-muted-foreground">
            {presentCount}/{INC043_CONTRACT_SECTIONS.length} sections mapped · {completeCount} with
            questions
          </p>
        </div>
      </div>
      <ul className={cn('space-y-2', compact && 'grid gap-2 sm:grid-cols-2')}>
        {checklist.map((item) => (
          <li
            key={item.key}
            className={cn(
              'flex items-start gap-2 rounded-md border border-border px-3 py-2 text-sm',
              item.status === 'missing' && 'border-dashed bg-muted/30',
            )}
          >
            {statusIcon(item.status)}
            <div className="min-w-0">
              <p className="font-medium text-foreground">{item.title}</p>
              {!compact ? (
                <p className="text-xs text-muted-foreground mt-0.5">{item.summary}</p>
              ) : null}
              <p className="text-xs text-muted-foreground mt-0.5">{statusLabel(item.status)}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
