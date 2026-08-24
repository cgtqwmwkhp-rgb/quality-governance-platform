import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight } from 'lucide-react'
import { Badge, Button } from '../../../components/ui'
import type { CellAggregateViewProps } from './cellAggregateTypes'

/** Live Certs panel — Assurance Cert Shelf items as framework/clause proof. */
export function CertsPanelSlot({
  data,
  loading,
  error,
}: CellAggregateViewProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-3" data-testid="workspace-panel-certs">
      <Button variant="outline" size="sm" asChild>
        <Link to="/assurance/certificates" data-testid="workspace-deep-link-certs">
          {t('compliance.standards_workspace.open_certs', {
            defaultValue: 'Open Certificate Shelf',
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

      {data && data.certificates.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="workspace-certs-empty">
          {t('compliance.standards_workspace.empty.certs', {
            defaultValue: 'No certificate shelf items linked as proof for this framework yet.',
          })}
        </p>
      ) : null}

      {data && data.certificates.length > 0 ? (
        <ul className="space-y-2" data-testid="workspace-certs-list">
          {data.certificates.slice(0, 12).map((cert) => (
            <li key={cert.shelf_key} className="rounded-md border border-border px-3 py-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={cert.detail_path || '/assurance/certificates'}
                  className="font-medium hover:underline"
                >
                  {cert.name}
                </Link>
                {cert.readiness_status ? <Badge variant="secondary">{cert.readiness_status}</Badge> : null}
                <Badge variant={cert.proof_scope === 'unmatched' ? 'secondary' : 'outline'}>
                  {cert.proof_scope === 'clause'
                    ? t('compliance.standards_workspace.proof.clause', { defaultValue: 'Clause proof' })
                    : cert.proof_scope === 'unmatched'
                      ? t('compliance.standards_workspace.proof.unmatched', {
                          defaultValue: 'On the shelf — proves no framework',
                        })
                      : t('compliance.standards_workspace.proof.framework', {
                          defaultValue: 'Framework proof',
                        })}
                </Badge>
              </div>
              {cert.expiry_date ? (
                <p className="text-xs text-muted-foreground mt-1">
                  {t('compliance.standards_workspace.expires', {
                    defaultValue: 'Expires',
                  })}
                  : {cert.expiry_date}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
