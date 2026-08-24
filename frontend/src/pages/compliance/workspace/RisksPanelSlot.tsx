import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight } from 'lucide-react'
import { Badge, Button } from '../../../components/ui'
import type { CellAggregateViewProps } from './cellAggregateTypes'

/**
 * Live Risks panel — register deep-links for the cell.
 * Clause 6.1.2 is treated as risk context (trap respect): links only, never invented coverage.
 */
export function RisksPanelSlot({
  data,
  loading,
  error,
  clauseNumber,
}: CellAggregateViewProps) {
  const { t } = useTranslation()
  const isRiskClause = (clauseNumber || '').trim().startsWith('6.1')

  return (
    <div className="space-y-3" data-testid="workspace-panel-risks">
      <Button variant="outline" size="sm" asChild>
        <Link to="/risk-register" data-testid="workspace-deep-link-risks">
          {t('compliance.standards_workspace.open_risks', { defaultValue: 'Open Risk Register' })}
          <ArrowUpRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
        </Link>
      </Button>

      {isRiskClause ? (
        <p className="text-xs text-muted-foreground" data-testid="workspace-risks-trap-note">
          {t('compliance.standards_workspace.risks_trap_note', {
            defaultValue:
              'Clause 6.1.x is risk-context — linked risks are shown honestly and do not invent coverage.',
          })}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted-foreground">{t('compliance.standards_workspace.loading', { defaultValue: 'Loading live graph…' })}</p>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {data && data.risks.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="workspace-risks-empty">
          {t('compliance.standards_workspace.empty.risks', {
            defaultValue: 'No linked risks for this clause.',
          })}
        </p>
      ) : null}

      {data && data.risks.length > 0 ? (
        <ul className="space-y-2" data-testid="workspace-risks-list">
          {data.risks.slice(0, 12).map((risk) => (
            <li key={`${risk.register}-${risk.id}`} className="rounded-md border border-border px-3 py-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Link to={risk.detail_path || '/risk-register'} className="font-medium hover:underline">
                  {risk.reference || `#${risk.id}`} · {risk.title}
                </Link>
                {risk.status ? <Badge variant="secondary">{risk.status}</Badge> : null}
                <Badge variant="outline">{risk.register}</Badge>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
