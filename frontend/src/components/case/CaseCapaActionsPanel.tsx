import { CheckCircle, ClipboardList, ExternalLink, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Action } from '../../api/client'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { cn } from '../../helpers/utils'

export type CaseCapaSource = 'incident' | 'near_miss' | 'rta' | 'complaint'

const I18N_PREFIX: Record<CaseCapaSource, string> = {
  incident: 'incidents.detail',
  near_miss: 'near_misses.detail',
  rta: 'rtas.detail',
  complaint: 'complaints.detail',
}

type CaseCapaActionsPanelProps = {
  sourceType: CaseCapaSource
  actions: Action[]
  onAdd: () => void
  onOpen: (action: Action) => void
  /** Optional test id prefix, e.g. "incident" → incident-capa-actions-panel */
  testIdPrefix?: string
  loading?: boolean
  unavailable?: boolean
}

/**
 * Shared CAPA / Actions tab body matching RTADetail: full list, empty state, Add.
 */
export function CaseCapaActionsPanel({
  sourceType,
  actions,
  onAdd,
  onOpen,
  testIdPrefix,
  loading = false,
  unavailable = false,
}: CaseCapaActionsPanelProps) {
  const { t } = useTranslation()
  const prefix = I18N_PREFIX[sourceType]
  const panelId = testIdPrefix ? `${testIdPrefix}-capa-actions-panel` : undefined

  return (
    <Card data-testid={panelId}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <ClipboardList className="w-5 h-5 text-primary" />
          {t(`${prefix}.actions_count`, {
            count: actions.length,
            defaultValue: `Actions (${actions.length})`,
          })}
        </CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={onAdd}
          disabled={loading || unavailable}
          data-testid={testIdPrefix ? `${testIdPrefix}-capa-add` : undefined}
        >
          <Plus className="w-4 h-4 mr-1" />
          {t('common.add', 'Add')}
        </Button>
      </CardHeader>
      <CardContent>
        {unavailable ? (
          <p className="text-sm text-amber-700 dark:text-amber-400" role="status">
            {t(
              `${prefix}.actions_unavailable`,
              'CAPA actions could not be loaded — counts may be incomplete.',
            )}
          </p>
        ) : loading ? (
          <p className="text-sm text-muted-foreground py-6 text-center">{t('common.loading', 'Loading…')}</p>
        ) : actions.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>{t(`${prefix}.no_actions`, 'No actions yet')}</p>
            <p className="text-sm">
              {t(`${prefix}.no_actions_description`, 'Add an action to track follow-up work')}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {actions.map((action) => (
              <div
                key={action.id}
                className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => onOpen(action)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onOpen(action)
                  }
                }}
                role="button"
                tabIndex={0}
                data-testid={
                  testIdPrefix ? `${testIdPrefix}-capa-action-${action.id}` : undefined
                }
              >
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center',
                      action.status === 'completed'
                        ? 'bg-success/10 text-success'
                        : action.status === 'cancelled'
                          ? 'bg-destructive/10 text-destructive'
                          : 'bg-warning/10 text-warning',
                    )}
                  >
                    <CheckCircle className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="font-medium text-foreground">{action.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {action.due_date
                        ? t(`${prefix}.due`, {
                            date: new Date(action.due_date).toLocaleDateString(),
                            defaultValue: `Due: ${new Date(action.due_date).toLocaleDateString()}`,
                          })
                        : t(`${prefix}.no_due_date`, 'No due date')}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      action.status === 'completed'
                        ? 'resolved'
                        : action.status === 'cancelled'
                          ? 'destructive'
                          : action.status === 'in_progress'
                            ? 'in-progress'
                            : ('secondary' as 'secondary')
                    }
                  >
                    {(action.status || 'open').replace(/_/g, ' ')}
                  </Badge>
                  <ExternalLink className="w-4 h-4 text-muted-foreground" />
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

type CaseCapaHeaderButtonProps = {
  sourceType: CaseCapaSource
  actionsCount: number
  capaHref: string
  onAdd: () => void
  onOpenCapa: () => void
  disabled?: boolean
  testIdPrefix?: string
}

/** RTA-style header: Open CAPA when linked actions exist, else Add Action. */
export function CaseCapaHeaderButton({
  sourceType,
  actionsCount,
  onAdd,
  onOpenCapa,
  disabled = false,
  testIdPrefix,
}: Omit<CaseCapaHeaderButtonProps, 'capaHref'> & { capaHref?: string }) {
  const { t } = useTranslation()
  const prefix = I18N_PREFIX[sourceType]

  if (actionsCount > 0) {
    return (
      <Button
        variant="outline"
        onClick={onOpenCapa}
        disabled={disabled}
        data-testid={testIdPrefix ? `${testIdPrefix}-open-capa` : undefined}
      >
        <ClipboardList className="w-4 h-4 mr-2" />
        {t(`${prefix}.open_capa`, {
          count: actionsCount,
          defaultValue: `Open CAPA (${actionsCount})`,
        })}
      </Button>
    )
  }

  return (
    <Button
      variant="outline"
      onClick={onAdd}
      disabled={disabled}
      data-testid={testIdPrefix ? `${testIdPrefix}-add-action` : undefined}
    >
      <Plus className="w-4 h-4 mr-2" />
      {t(`${prefix}.add_action`, 'Add Action')}
    </Button>
  )
}
