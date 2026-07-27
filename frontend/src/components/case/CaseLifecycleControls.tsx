/**
 * Header Close / Reopen control shared by the four case registers.
 *
 * One component so closure looks and behaves identically on every case type:
 * a non-closed case offers Close (via the summary dialog), a closed one offers
 * Reopen along the single reverse edge the API allows.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, Loader2, RotateCcw } from 'lucide-react'
import { Button } from '../ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/Dialog'
import { CaseCloseSummaryDialog } from './CaseCloseSummaryDialog'
import {
  CASE_REOPEN_STATUS,
  isCaseClosed,
  type CaseClosureCaseType,
} from '../../api/caseClosureClient'
import { formatCodedValue } from '../../helpers/displayLabels'

export interface CaseLifecycleControlsProps {
  caseType: CaseClosureCaseType
  caseId: number
  status?: string | null
  /** Persist the close; reject to keep the summary dialog open with the error. */
  onClose: (payload: { lessons_learnt?: string }) => Promise<void>
  /** Persist the reopen; the reverse status is `CASE_REOPEN_STATUS[caseType]`. */
  onReopen: () => Promise<void>
  onOpenActions?: () => void
  disabled?: boolean
  testIdPrefix?: string
  /** Optional external control, so Edit → Closed can open the same dialog. */
  closeDialogOpen?: boolean
  onCloseDialogOpenChange?: (open: boolean) => void
}

export function CaseLifecycleControls({
  caseType,
  caseId,
  status,
  onClose,
  onReopen,
  onOpenActions,
  disabled = false,
  testIdPrefix = 'case',
  closeDialogOpen,
  onCloseDialogOpenChange,
}: CaseLifecycleControlsProps) {
  const { t } = useTranslation()
  const [internalCloseOpen, setInternalCloseOpen] = useState(false)
  const [reopenOpen, setReopenOpen] = useState(false)
  const [reopening, setReopening] = useState(false)

  const closeOpen = closeDialogOpen ?? internalCloseOpen
  const setCloseOpen = (open: boolean) => {
    setInternalCloseOpen(open)
    onCloseDialogOpenChange?.(open)
  }

  const closed = isCaseClosed(caseType, status)

  const handleReopen = async () => {
    setReopening(true)
    try {
      await onReopen()
      setReopenOpen(false)
    } finally {
      setReopening(false)
    }
  }

  if (closed) {
    return (
      <>
        <Button
          variant="outline"
          onClick={() => setReopenOpen(true)}
          disabled={disabled}
          data-testid={`${testIdPrefix}-reopen`}
        >
          <RotateCcw className="w-4 h-4 mr-2" aria-hidden="true" />
          {t('caseClosure.reopen', 'Reopen')}
        </Button>
        <Dialog open={reopenOpen} onOpenChange={setReopenOpen}>
          <DialogContent data-testid={`${testIdPrefix}-reopen-dialog`}>
            <DialogHeader>
              <DialogTitle>{t('caseClosure.reopenTitle', 'Reopen this case?')}</DialogTitle>
              <DialogDescription>
                {t('caseClosure.reopenDescription', {
                  defaultValue:
                    'The case moves back to {{status}} and its closure stamp is cleared. The audit trail keeps the original close.',
                  status: formatCodedValue(CASE_REOPEN_STATUS[caseType]),
                })}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setReopenOpen(false)} disabled={reopening}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button
                onClick={() => void handleReopen()}
                disabled={reopening}
                data-testid={`${testIdPrefix}-reopen-confirm`}
              >
                {reopening ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" aria-hidden="true" />
                ) : null}
                {t('caseClosure.reopen', 'Reopen')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    )
  }

  return (
    <>
      <Button
        variant="outline"
        onClick={() => setCloseOpen(true)}
        disabled={disabled}
        data-testid={`${testIdPrefix}-close`}
      >
        <CheckCircle2 className="w-4 h-4 mr-2" aria-hidden="true" />
        {t('caseClosure.close', 'Close case')}
      </Button>
      <CaseCloseSummaryDialog
        open={closeOpen}
        caseType={caseType}
        caseId={caseId}
        onConfirm={onClose}
        onOpenChange={setCloseOpen}
        onOpenActions={onOpenActions}
        testIdPrefix={testIdPrefix}
      />
    </>
  )
}
