import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/Label'
import { Textarea } from '../../components/ui/Textarea'
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../../components/ui/Sheet'
import { complianceScheduleApi } from '../../api/client'
import type { CompleteRecordPayload } from '../../api/complianceScheduleClient'
import { toast } from '../../contexts/ToastContext'

interface RecordCompletionSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  requirementId: number
  requirementTitle: string
  nextDueDate: string
  onCompleted: () => void
}

export function RecordCompletionSheet({
  open,
  onOpenChange,
  requirementId,
  requirementTitle,
  nextDueDate,
  onCompleted,
}: RecordCompletionSheetProps) {
  const { t } = useTranslation()
  const [notes, setNotes] = useState('')
  const [checkPassed, setCheckPassed] = useState(true)
  const [completedAt, setCompletedAt] = useState(() => new Date().toISOString().slice(0, 16))
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const payload: CompleteRecordPayload = {
        notes: notes.trim() || undefined,
        check_passed: checkPassed,
        completed_at: completedAt ? new Date(completedAt).toISOString() : undefined,
      }
      await complianceScheduleApi.completeRequirement(requirementId, payload)
      toast.success(t('compliance.schedule.complete.success', 'Occurrence recorded'))
      onOpenChange(false)
      setNotes('')
      onCompleted()
    } catch {
      toast.error(t('compliance.schedule.complete.error', 'Could not complete this occurrence'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" data-testid="compliance-schedule-complete-sheet">
        <SheetHeader>
          <SheetTitle>{t('compliance.schedule.complete.title', 'Record completion')}</SheetTitle>
          <SheetDescription>
            {requirementTitle} — {t('compliance.schedule.due', 'Due')} {nextDueDate}
          </SheetDescription>
        </SheetHeader>
        <SheetBody className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="cs-completed-at">
              {t('compliance.schedule.complete.completed_at', 'Completed at')}
            </Label>
            <Input
              id="cs-completed-at"
              type="datetime-local"
              value={completedAt}
              onChange={(e) => setCompletedAt(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              id="cs-check-passed"
              type="checkbox"
              className="h-4 w-4"
              checked={checkPassed}
              onChange={(e) => setCheckPassed(e.target.checked)}
            />
            <Label htmlFor="cs-check-passed">
              {t('compliance.schedule.complete.check_passed', 'Check passed')}
            </Label>
          </div>
          <div className="space-y-2">
            <Label htmlFor="cs-notes">{t('compliance.schedule.complete.notes', 'Notes')}</Label>
            <Textarea
              id="cs-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
            />
          </div>
          <Button
            data-testid="compliance-schedule-complete-submit"
            disabled={submitting}
            onClick={() => void handleSubmit()}
          >
            {submitting
              ? t('common.saving', 'Saving…')
              : t('compliance.schedule.complete.submit', 'Complete occurrence')}
          </Button>
        </SheetBody>
      </SheetContent>
    </Sheet>
  )
}

export default RecordCompletionSheet
