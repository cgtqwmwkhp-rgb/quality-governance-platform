import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight } from 'lucide-react'
import { Badge, Button } from '../../../components/ui'
import type { CellAggregateViewProps } from './cellAggregateTypes'

/** Live Evidence panel — CEL rows for the cell (conformance vs operational signals). */
export function EvidencePanelSlot({
  data,
  loading,
  error,
  clauseNumber,
}: CellAggregateViewProps) {
  const { t } = useTranslation()
  const evidenceHref = clauseNumber
    ? `/compliance?view=evidence&clause=${encodeURIComponent(clauseNumber)}`
    : '/compliance?view=evidence'

  return (
    <div className="space-y-3" data-testid="workspace-panel-evidence">
      <Button variant="outline" size="sm" asChild>
        <Link to={evidenceHref} data-testid="workspace-deep-link-evidence">
          {t('compliance.standards_workspace.open_evidence_centre', {
            defaultValue: 'Open Evidence Centre',
          })}
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

      {data?.cover_blocked ? (
        <p className="text-sm text-amber-800 dark:text-amber-300" data-testid="workspace-evidence-cover-block">
          {t('compliance.standards_workspace.cover_blocked', {
            defaultValue: 'Cover blocked: open NC and/or open action on this clause.',
          })}
        </p>
      ) : null}

      {data && data.evidence.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="workspace-evidence-empty">
          {t('compliance.standards_workspace.empty.evidence', {
            defaultValue: 'No evidence links for this clause yet.',
          })}
        </p>
      ) : null}

      {data && data.evidence.length > 0 ? (
        <ul className="space-y-2" data-testid="workspace-evidence-list">
          {data.evidence.slice(0, 12).map((row) => (
            <li key={row.id} className="rounded-md border border-border px-3 py-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{row.title || `${row.entity_type}:${row.entity_id}`}</span>
                <Badge variant="outline">{row.entity_type}</Badge>
                {row.is_operational_signal ? (
                  <Badge variant="destructive">{row.signal_type || 'signal'}</Badge>
                ) : (
                  <Badge variant="secondary">
                    {row.signal_type || t('compliance.standards_workspace.evidence', { defaultValue: 'evidence' })}
                  </Badge>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
