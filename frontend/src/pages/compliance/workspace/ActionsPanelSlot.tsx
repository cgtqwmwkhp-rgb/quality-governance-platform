import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight } from 'lucide-react'
import { Badge, Button } from '../../../components/ui'
import type { CellAggregateViewProps } from './cellAggregateTypes'

/** Live Actions panel — capa_actions joined for the cell (cover gate input). */
export function ActionsPanelSlot({
  data,
  loading,
  error,
  clauseNumber,
}: CellAggregateViewProps) {
  const { t } = useTranslation()
  const href = clauseNumber
    ? `/actions?clause=${encodeURIComponent(clauseNumber)}`
    : '/actions'

  return (
    <div className="space-y-3" data-testid="workspace-panel-actions">
      <Button variant="outline" size="sm" asChild>
        <Link to={href} data-testid="workspace-deep-link-actions">
          {t('compliance.standards_workspace.open_actions', { defaultValue: 'Open Actions' })}
          <ArrowUpRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
        </Link>
      </Button>

      {loading ? (
        <p className="text-sm text-muted-foreground">{t('compliance.standards_workspace.loading', { defaultValue: 'Loading live graph…' })}</p>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {data?.cover_blocked && (data.summary.open_action_count ?? 0) > 0 ? (
        <p className="text-sm text-amber-800 dark:text-amber-300" data-testid="workspace-actions-cover-block">
          {t('compliance.standards_workspace.cover_blocked_actions', {
            defaultValue: 'Open action(s) block this cell from showing Covered.',
          })}
        </p>
      ) : null}

      {data && data.actions.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="workspace-actions-empty">
          {t('compliance.standards_workspace.empty.actions', {
            defaultValue: 'No linked actions / CAPA for this clause.',
          })}
        </p>
      ) : null}

      {data && data.actions.length > 0 ? (
        <ul className="space-y-2" data-testid="workspace-actions-list">
          {data.actions.slice(0, 12).map((action) => (
            <li key={action.id} className="rounded-md border border-border px-3 py-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Link to={action.detail_path || `/actions/${action.id}`} className="font-medium hover:underline">
                  {action.reference_number || `#${action.id}`} · {action.title}
                </Link>
                <Badge variant="secondary">{action.status}</Badge>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
