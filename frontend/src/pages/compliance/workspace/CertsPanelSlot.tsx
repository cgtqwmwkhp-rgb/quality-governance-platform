import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight } from 'lucide-react'
import { Button } from '../../../components/ui'

/** Thin honest stub — PR-B live graph fills Certs. */
export function CertsPanelSlot() {
  const { t } = useTranslation()
  return (
    <div className="space-y-3" data-testid="workspace-panel-certs">
      <p className="text-sm text-muted-foreground">
        {t('compliance.standards_workspace.stub.certs', {
          defaultValue: 'PR-B live graph fills this Certs panel.',
        })}
      </p>
      <Button variant="outline" size="sm" asChild>
        <Link to="/assurance/certificates" data-testid="workspace-deep-link-certs">
          {t('compliance.standards_workspace.open_certs', {
            defaultValue: 'Open Certificate Shelf',
          })}
          <ArrowUpRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
        </Link>
      </Button>
    </div>
  )
}
