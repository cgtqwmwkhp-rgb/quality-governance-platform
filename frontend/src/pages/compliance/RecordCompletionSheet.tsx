import { useEffect, useRef, useState } from 'react'
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
import { complianceScheduleApi, evidenceAssetsApi } from '../../api/client'
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

/**
 * Staff evidence upload requires an existing source row for
 * ``compliance_record``. Completion creates that row, and
 * ``evidence_asset_ids`` on the complete payload rebinds pre-uploaded assets
 * onto it in the same transaction.
 *
 * Until the occurrence exists we cannot upload as ``compliance_record``. The
 * upload route skips existence checks for ``induction`` (unlike
 * ``evidence_service``), so staged files park briefly as
 * ``induction`` / requirement id, then the complete call rebinds them. If
 * complete fails, staged assets are deleted.
 */
const STAGING_SOURCE_MODULE = 'induction'

function nowLocalInputValue() {
  return new Date().toISOString().slice(0, 16)
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
  const [completedAt, setCompletedAt] = useState(nowLocalInputValue)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [submitting, setSubmitting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Reopening must not show the last attempt's typing (notes, timestamp, files).
  useEffect(() => {
    if (!open) return
    setNotes('')
    setCheckPassed(true)
    setCompletedAt(nowLocalInputValue())
    setPendingFiles([])
    setSubmitting(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [open])

  const handleFilesSelected = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : []
    if (fileInputRef.current) fileInputRef.current.value = ''
    if (files.length === 0) return
    setPendingFiles((prev) => [...prev, ...files])
  }

  const removePendingFile = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    const stagedIds: number[] = []
    try {
      for (const file of pendingFiles) {
        const uploaded = await evidenceAssetsApi.upload(file, {
          source_module: STAGING_SOURCE_MODULE,
          source_id: requirementId,
          title: file.name,
          description: `compliance-schedule-complete-staging:${requirementId}`,
          visibility: 'internal_customer',
        })
        stagedIds.push(uploaded.data.id)
      }

      const payload: CompleteRecordPayload = {
        notes: notes.trim() || undefined,
        check_passed: checkPassed,
        completed_at: completedAt ? new Date(completedAt).toISOString() : undefined,
        evidence_asset_ids: stagedIds.length > 0 ? stagedIds : undefined,
      }
      await complianceScheduleApi.completeRequirement(requirementId, payload)
      toast.success(t('compliance.schedule.complete.success', 'Occurrence recorded'))
      onOpenChange(false)
      onCompleted()
    } catch {
      if (stagedIds.length > 0) {
        await Promise.allSettled(stagedIds.map((id) => evidenceAssetsApi.delete(id)))
      }
      toast.error(
        pendingFiles.length > 0
          ? t(
              'compliance.schedule.complete.evidence_error',
              'Could not complete this occurrence. Staged evidence was discarded — try again.',
            )
          : t('compliance.schedule.complete.error', 'Could not complete this occurrence'),
      )
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
          <div className="space-y-2" data-testid="compliance-schedule-complete-evidence">
            <Label htmlFor="cs-evidence">
              {t('compliance.schedule.complete.evidence', 'Upload proof of completion')}
            </Label>
            <p className="text-xs text-muted-foreground">
              {t(
                'compliance.schedule.complete.evidence_hint',
                'Attach certificates, reports, or photos now. They are linked to this occurrence when you complete it.',
              )}
            </p>
            <input
              ref={fileInputRef}
              id="cs-evidence"
              type="file"
              multiple
              className="hidden"
              data-testid="compliance-schedule-complete-evidence-input"
              onChange={handleFilesSelected}
              disabled={submitting}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              data-testid="compliance-schedule-complete-evidence-add"
              disabled={submitting}
              onClick={() => fileInputRef.current?.click()}
            >
              {t('compliance.schedule.complete.evidence_add', 'Upload proof files')}
            </Button>
            {pendingFiles.length > 0 && (
              <ul className="space-y-1 text-sm" data-testid="compliance-schedule-complete-evidence-list">
                {pendingFiles.map((file, index) => (
                  <li
                    key={`${file.name}-${file.size}-${index}`}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="truncate">{file.name}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-auto shrink-0 px-2 py-1 text-xs"
                      data-testid={`compliance-schedule-complete-evidence-remove-${index}`}
                      disabled={submitting}
                      onClick={() => removePendingFile(index)}
                    >
                      {t('common.remove', 'Remove')}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
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
