import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight } from 'lucide-react'
import { Button } from '../../../components/ui'

/** Thin honest stub — PR-B live graph fills Evidence. */
export function EvidencePanelSlot({ clauseNumber }: { clauseNumber?: string | null }) {
  const { t } = useTranslation()
  const evidenceHref = clauseNumber
    ? `/compliance?view=evidence&clause=${encodeURIComponent(clauseNumber)}`
    : '/compliance?view=evidence'

  return (
    <div className="space-y-3" data-testid="workspace-panel-evidence">
      <p className="text-sm text-muted-foreground">
        {t('compliance.standards_workspace.stub.evidence', {
          defaultValue: 'PR-B live graph fills this Evidence panel.',
        })}
      </p>
      <Button variant="outline" size="sm" asChild>
        <Link to={evidenceHref} data-testid="workspace-deep-link-evidence">
          {t('compliance.standards_workspace.open_evidence_centre', {
            defaultValue: 'Open Evidence Centre',
          })}
          <ArrowUpRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
        </Link>
      </Button>
    </div>
  )
}
