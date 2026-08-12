import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight, ClipboardCheck } from 'lucide-react'
import { Button } from '../../../components/ui'

/** Thin honest stub — PR-B live graph fills Audits & NC. */
export function AuditsNcPanelSlot({ clauseNumber }: { clauseNumber?: string | null }) {
  const { t } = useTranslation()
  const href = clauseNumber
    ? `/audits?view=findings&clause=${encodeURIComponent(clauseNumber)}`
    : '/audits'

  return (
    <div className="space-y-3" data-testid="workspace-panel-audits">
      <p className="text-sm text-muted-foreground">
        {t('compliance.standards_workspace.stub.audits', {
          defaultValue: 'PR-B live graph fills this Audits & NC panel.',
        })}
      </p>
      <Button variant="outline" size="sm" asChild>
        <Link to={href} data-testid="workspace-deep-link-audits">
          <ClipboardCheck className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
          {t('compliance.standards_workspace.open_audits', { defaultValue: 'Open Audits' })}
          <ArrowUpRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
        </Link>
      </Button>
    </div>
  )
}
