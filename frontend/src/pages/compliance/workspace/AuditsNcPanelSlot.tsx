import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight, ClipboardCheck, Flag, Upload } from 'lucide-react'
import { Badge, Button } from '../../../components/ui'
import { AUDITS_IMPORT_MODAL_PATH } from '../../customerAuditsHelpers'
import type { CellAggregateViewProps } from './cellAggregateTypes'

/** Live Audits & NC panel — findings from cell aggregate + prior import CTA. */
export function AuditsNcPanelSlot({
  data,
  loading,
  error,
  clauseNumber,
}: CellAggregateViewProps) {
  const { t } = useTranslation()
  const href = clauseNumber
    ? `/audits?view=findings&clause=${encodeURIComponent(clauseNumber)}`
    : '/audits'

  return (
    <div className="space-y-3" data-testid="workspace-panel-audits">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" asChild>
          <Link to={href} data-testid="workspace-deep-link-audits">
            <ClipboardCheck className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
            {t('compliance.standards_workspace.open_audits', { defaultValue: 'Open Audits' })}
            <ArrowUpRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
          </Link>
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link to={AUDITS_IMPORT_MODAL_PATH} data-testid="workspace-prior-outcome-upload">
            <Upload className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
            {t('compliance.standards_workspace.upload_prior_outcome', {
              defaultValue: 'Upload prior audit outcome',
            })}
          </Link>
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground" data-testid="workspace-audits-loading">
          {t('compliance.standards_workspace.loading', { defaultValue: 'Loading live graph…' })}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" role="alert" data-testid="workspace-audits-error">
          {error}
        </p>
      ) : null}

      {data?.recurrence_red_flag ? (
        <div
          className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          data-testid="workspace-recurrence-flag"
        >
          <Flag className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            {t('compliance.standards_workspace.recurrence', {
              defaultValue: 'Recurrence: an NC on this clause reappeared after a prior close.',
            })}
          </span>
        </div>
      ) : null}

      {data && data.findings.length === 0 && data.imported_priors.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="workspace-audits-empty">
          {t('compliance.standards_workspace.empty.audits', {
            defaultValue: 'No linked findings or imported priors for this clause yet.',
          })}
        </p>
      ) : null}

      {data && data.findings.length > 0 ? (
        <ul className="space-y-2" data-testid="workspace-audits-findings">
          {data.findings.slice(0, 12).map((finding) => (
            <li
              key={finding.id}
              className="rounded-md border border-border px-3 py-2 text-sm"
              data-testid={`workspace-finding-${finding.id}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Link to={finding.detail_path || href} className="font-medium text-foreground hover:underline">
                  {finding.reference_number || `#${finding.id}`} · {finding.title}
                </Link>
                <Badge variant="secondary">{finding.status}</Badge>
                {finding.audit_kind === 'mock' ? (
                  <Badge variant="outline" data-testid={`workspace-finding-mock-${finding.id}`}>
                    {t('compliance.standards_workspace.kind.mock', { defaultValue: 'Mock audit' })}
                  </Badge>
                ) : null}
                {finding.audit_kind === 'imported' ? (
                  <Badge variant="outline">
                    {t('compliance.standards_workspace.kind.imported', { defaultValue: 'Imported' })}
                  </Badge>
                ) : null}
                {finding.is_nc ? (
                  <Badge variant="destructive">
                    {t('compliance.standards_workspace.nc', { defaultValue: 'NC' })}
                  </Badge>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {data && data.imported_priors.length > 0 ? (
        <div className="space-y-2" data-testid="workspace-imported-priors">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            {t('compliance.standards_workspace.imported_priors', {
              defaultValue: 'Imported prior outcomes',
            })}
          </p>
          <ul className="space-y-2">
            {data.imported_priors.slice(0, 6).map((prior) => (
              <li key={prior.id} className="rounded-md border border-border px-3 py-2 text-sm">
                <Link to={prior.detail_path || '/compliance?view=evidence&section=imported'} className="hover:underline">
                  {prior.scheme_label || prior.scheme}
                  {prior.outcome_status ? ` · ${prior.outcome_status}` : ''}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
