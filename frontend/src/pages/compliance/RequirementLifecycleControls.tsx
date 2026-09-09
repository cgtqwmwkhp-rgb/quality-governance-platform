import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../../components/ui/AlertDialog'
import { Button } from '../../components/ui/Button'
import { complianceScheduleApi, getApiErrorMessage } from '../../api/client'
import type { ComplianceRequirement } from '../../api/complianceScheduleClient'
import { toast } from '../../contexts/ToastContext'

export interface RequirementLifecycleControlsProps {
  requirement: ComplianceRequirement
  onChanged: () => void
}

/**
 * Retire an obligation, or bring a retired one back.
 *
 * Both directions ship together on purpose. Deactivation is recoverable in the
 * data — it only sets a flag — but without a way back in the interface it would
 * read to the user as deletion, and the obligation would vanish from the only
 * screen that lists it.
 */
export function RequirementLifecycleControls({
  requirement,
  onChanged,
}: RequirementLifecycleControlsProps) {
  const { t, i18n } = useTranslation()
  const copy = (key: string, english: string) =>
    i18n.language.toLowerCase().startsWith('cy') ? t(key, english) : english
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const deactivate = useCallback(async () => {
    setBusy(true)
    try {
      await complianceScheduleApi.deactivateRequirement(requirement.id)
      setConfirmOpen(false)
      toast.success(
        t('compliance.schedule.deactivate.success', 'Obligation retired. Reminders have stopped.'),
      )
      onChanged()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }, [requirement.id, onChanged, t])

  const reactivate = useCallback(async () => {
    setBusy(true)
    try {
      // No dedicated endpoint; is_active is an ordinary updatable field and the
      // read path returns inactive rows, so the obligation can be fetched and
      // flipped back without resorting to a second activation, which would
      // create a duplicate rather than restore this one.
      await complianceScheduleApi.updateRequirement(requirement.id, { is_active: true })
      toast.success(
        t('compliance.schedule.reactivate.success', 'Obligation restored. Reminders resume.'),
      )
      onChanged()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }, [requirement.id, onChanged, t])

  if (!requirement.is_active) {
    return (
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => void reactivate()}
        data-testid="compliance-schedule-reactivate"
      >
        {t('compliance.schedule.reactivate.cta', 'Reactivate')}
      </Button>
    )
  }

  return (
    <>
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => setConfirmOpen(true)}
        data-testid="compliance-schedule-deactivate"
      >
        {t('compliance.schedule.deactivate.cta', 'Retire')}
      </Button>
      <AlertDialog open={confirmOpen} onOpenChange={(open) => !open && setConfirmOpen(false)}>
        <AlertDialogContent
          className="max-w-md"
          data-testid="compliance-schedule-deactivate-confirm"
        >
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('compliance.schedule.deactivate.title', 'Retire this obligation?')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {copy(
                'compliance.schedule.deactivate.description',
                'It leaves the active register and stops generating reminders. Its completion history is kept, and you can bring it back from the Retired view.',
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              data-testid="compliance-schedule-deactivate-cancel"
            >
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={busy}
              onClick={() => void deactivate()}
              data-testid="compliance-schedule-deactivate-confirm-action"
            >
              {busy
                ? t('common.saving', 'Saving…')
                : t('compliance.schedule.deactivate.confirm', 'Retire obligation')}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
