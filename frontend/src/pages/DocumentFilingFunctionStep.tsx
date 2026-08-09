/**
 * L-18 Function confirm step (WD-1 scaffold).
 *
 * Loads the WA-2 controlled vocabulary and lets the filer confirm an owning
 * function before upload. Confirming sends `function_code` on the existing
 * upload API (PEL allocated server-side). Skipping is allowed in this prep
 * slice because the API still accepts omit — full "required at file" lands
 * with the WD-1 product slice after WC-1 LIVE.
 */
import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import api, { getApiErrorMessage } from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Label } from '../components/ui/Label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import {
  formatFunctionOptionLabel,
  type DocumentFunctionOption,
} from './documentFilingWizard'

const NONE_VALUE = '__none__'

export interface DocumentFilingFunctionStepProps {
  fileName: string
  busy?: boolean
  onConfirm: (functionCode: string | null) => void
  onBack: () => void
}

export function DocumentFilingFunctionStep({
  fileName,
  busy = false,
  onConfirm,
  onBack,
}: DocumentFilingFunctionStepProps) {
  const { t } = useTranslation()
  const [functions, setFunctions] = useState<DocumentFunctionOption[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedCode, setSelectedCode] = useState<string>(NONE_VALUE)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const response = await api.get<DocumentFunctionOption[]>(
          '/api/v1/document-categories/functions',
        )
        if (cancelled) return
        const active = (response.data ?? []).filter((fn) => fn.active !== false)
        setFunctions(active)
      } catch (err) {
        if (cancelled) return
        const message = getApiErrorMessage(err)
        setLoadError(message)
        setFunctions([])
        toast.error(message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const confirmedCode = selectedCode === NONE_VALUE ? null : selectedCode

  return (
    <div className="space-y-4" data-testid="documents-filing-function-step">
      <div className="rounded-lg border border-border bg-surface/40 px-3 py-2">
        <p className="text-xs text-muted-foreground">{t('documents.filing.function.file_label')}</p>
        <p className="truncate text-sm font-medium text-foreground" data-testid="documents-filing-function-file">
          {fileName}
        </p>
      </div>

      <p className="text-sm text-muted-foreground">{t('documents.filing.function.helper')}</p>

      {loading ? (
        <div
          className="flex items-center gap-2 text-sm text-muted-foreground"
          data-testid="documents-filing-function-loading"
        >
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('documents.filing.function.loading')}
        </div>
      ) : loadError ? (
        <p
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          data-testid="documents-filing-function-error"
        >
          {loadError}
        </p>
      ) : (
        <div className="space-y-2">
          <Label htmlFor="documents-filing-function-select">
            {t('documents.filing.function.select_label')}
          </Label>
          <Select
            value={selectedCode}
            onValueChange={setSelectedCode}
            disabled={busy || functions.length === 0}
          >
            <SelectTrigger
              id="documents-filing-function-select"
              data-testid="documents-filing-function-select"
              aria-label={t('documents.filing.function.select_label')}
            >
              <SelectValue placeholder={t('documents.filing.function.select_placeholder')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>
                {t('documents.filing.function.skip_option')}
              </SelectItem>
              {functions.map((fn) => (
                <SelectItem key={fn.id} value={fn.code} data-testid={`documents-filing-function-option-${fn.code}`}>
                  {formatFunctionOptionLabel(fn)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {functions.length === 0 ? (
            <p className="text-xs text-muted-foreground" data-testid="documents-filing-function-empty">
              {t('documents.filing.function.empty')}
            </p>
          ) : null}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <Button
          variant="secondary"
          onClick={onBack}
          disabled={busy}
          data-testid="documents-filing-function-back"
        >
          {t('documents.filing.function.back')}
        </Button>
        <Button
          onClick={() => onConfirm(confirmedCode)}
          disabled={busy || loading}
          data-testid="documents-filing-function-continue"
        >
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {confirmedCode
            ? t('documents.filing.function.confirm_upload')
            : t('documents.filing.function.upload_without')}
        </Button>
      </div>
    </div>
  )
}

export default DocumentFilingFunctionStep
