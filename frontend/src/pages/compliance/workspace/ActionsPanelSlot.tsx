import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight } from 'lucide-react'
import { Button } from '../../../components/ui'

/** Thin honest stub — PR-B live graph fills Actions. */
export function ActionsPanelSlot() {
  const { t } = useTranslation()
  return (
    <div className="space-y-3" data-testid="workspace-panel-actions">
      <p className="text-sm text-muted-foreground">
        {t('compliance.standards_workspace.stub.actions', {
          defaultValue: 'PR-B live graph fills this Actions panel.',
        })}
      </p>
      <Button variant="outline" size="sm" asChild>
        <Link to="/actions" data-testid="workspace-deep-link-actions">
          {t('compliance.standards_workspace.open_actions', { defaultValue: 'Open Actions' })}
          <ArrowUpRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
        </Link>
      </Button>
    </div>
  )
}
