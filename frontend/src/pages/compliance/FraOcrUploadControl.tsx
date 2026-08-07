import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/Button'
import { complianceScheduleFraOcrApi, getApiErrorMessage } from '../../api/client'
import type { FraOcrDraftResponse } from '../../api/complianceScheduleFraOcrClient'
import { toast } from '../../contexts/ToastContext'

interface FraOcrUploadControlProps {
  requirementId: number
  onCreated: (draft: FraOcrDraftResponse) => void
  disabled?: boolean
}

/**
 * PDF file input that creates a pending FRA OCR draft. The review sheet is the
 * human gate — this control only uploads and hands the draft back.
 */
export function FraOcrUploadControl({
  requirementId,
  onCreated,
  disabled = false,
}: FraOcrUploadControlProps) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)

  const handleChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (inputRef.current) inputRef.current.value = ''
    if (!file) return

    setBusy(true)
    try {
      const response = await complianceScheduleFraOcrApi.createDraft(requirementId, file)
      toast.success(
        t('compliance.schedule.fra_ocr.upload.success', 'FRA report uploaded — review the proposal'),
      )
      onCreated(response.data)
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div data-testid="fra-ocr-upload">
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        data-testid="fra-ocr-upload-input"
        disabled={busy || disabled}
        onChange={(e) => void handleChange(e)}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={busy || disabled}
        data-testid="fra-ocr-upload-cta"
        onClick={() => inputRef.current?.click()}
      >
        {busy
          ? t('compliance.schedule.fra_ocr.upload.busy', 'Uploading…')
          : t('compliance.schedule.fra_ocr.upload.cta', 'Ingest FRA report')}
      </Button>
    </div>
  )
}
