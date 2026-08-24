/**
 * L-18c Bring under control — prep stub (WD-1 scaffold).
 *
 * Honest placeholder only. Full in-app path (uncontrolled Register row →
 * Function/Category → PEL → optional Related) waits for WC-1 LIVE (control
 * converge + legal holds). Do not invent a parallel control API here.
 */
import { ShieldAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/ui/Button'

export interface DocumentFilingControlStubProps {
  onDone: () => void
}

export function DocumentFilingControlStub({ onDone }: DocumentFilingControlStubProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4" data-testid="documents-filing-control-stub">
      <div className="flex items-start gap-3 rounded-lg border border-border bg-surface/40 px-3 py-3">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">
            {t('documents.filing.control_stub.title')}
          </p>
          <p className="text-sm text-muted-foreground">{t('documents.filing.control_stub.body')}</p>
        </div>
      </div>
      <div className="flex justify-end">
        <Button onClick={onDone} data-testid="documents-filing-control-done">
          {t('documents.filing.control_stub.done')}
        </Button>
      </div>
    </div>
  )
}

export default DocumentFilingControlStub
