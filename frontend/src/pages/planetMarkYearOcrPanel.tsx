import { useState } from 'react'
import { AlertTriangle, Loader2, ScanSearch, CheckCircle2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import i18n from 'i18next'
import { getApiErrorMessage, planetMarkApi } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import {
  OCR_PREVIEW_FIELD_KEYS,
  canApplyOcrPreview,
  formatOcrFieldDisplay,
  isExtractedField,
  isRetryableOcrError,
  needsXlsxOverwriteConfirmation,
  ocrFieldLabelKey,
  type PlanetMarkOcrExtractResponse,
  type PlanetMarkOcrApplyResponse,
} from './planetMarkYearOcrHelpers'

interface PlanetMarkYearOcrPanelProps {
  yearId: number
  yearLabel: string
  measurementReportEvidenceId: number | null
  certificateEvidenceId: number | null
  onApplied: () => void | Promise<void>
}

export function PlanetMarkYearOcrPanel({
  yearId,
  yearLabel,
  measurementReportEvidenceId,
  certificateEvidenceId,
  onApplied,
}: PlanetMarkYearOcrPanelProps) {
  const { t } = useTranslation()
  const [scanning, setScanning] = useState(false)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retryable, setRetryable] = useState(false)
  const [preview, setPreview] = useState<PlanetMarkOcrExtractResponse | null>(null)
  const [applyResult, setApplyResult] = useState<PlanetMarkOcrApplyResponse | null>(null)
  const [forceOverwrite, setForceOverwrite] = useState(false)

  const scanTargetId = measurementReportEvidenceId ?? certificateEvidenceId
  const documentKind = measurementReportEvidenceId
    ? 'measurement_report'
    : 'certificate'

  const runScan = async () => {
    if (!scanTargetId) {
      setError(t('planet_mark.shell.years.ocr.no_evidence'))
      setRetryable(false)
      return
    }
    setScanning(true)
    setError(null)
    setRetryable(false)
    setApplyResult(null)
    try {
      const response = await planetMarkApi.extractYearOcr(yearId, {
        evidenceId: scanTargetId,
        documentKind,
      })
      setPreview(response.data)
      setForceOverwrite(false)
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, i18n.t('planet_mark.shell.years.ocr.scan_error')))
      setRetryable(isRetryableOcrError(err))
      setPreview(null)
    } finally {
      setScanning(false)
    }
  }

  const runApply = async () => {
    if (!preview || !canApplyOcrPreview(preview)) return
    if (needsXlsxOverwriteConfirmation(preview) && !forceOverwrite) {
      setError(t('planet_mark.shell.years.ocr.xlsx_ssot_block'))
      setRetryable(false)
      return
    }
    setApplying(true)
    setError(null)
    try {
      const response = await planetMarkApi.applyYearOcr(yearId, {
        document_kind: preview.document_kind,
        force_overwrite_totals: forceOverwrite,
        preview,
      })
      setApplyResult(response.data)
      await onApplied()
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, i18n.t('planet_mark.shell.years.ocr.apply_error')))
      setRetryable(isRetryableOcrError(err))
    } finally {
      setApplying(false)
    }
  }

  return (
    <Card data-testid="planet-mark-years-ocr-panel">
      <CardHeader>
        <CardTitle>{t('planet_mark.shell.years.ocr.title')}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {t('planet_mark.shell.years.ocr.hint', { year: yearLabel })}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {!scanTargetId && (
          <div
            className="rounded-md border border-border bg-surface/40 p-3 text-sm text-muted-foreground"
            data-testid="planet-mark-years-ocr-empty"
          >
            {t('planet_mark.shell.years.ocr.no_evidence')}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={!scanTargetId || scanning}
            onClick={() => void runScan()}
            data-testid="planet-mark-years-ocr-scan"
          >
            {scanning ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <ScanSearch className="h-4 w-4" aria-hidden />
            )}
            {scanning
              ? t('planet_mark.shell.years.ocr.scanning')
              : t('planet_mark.shell.years.ocr.scan_cta')}
          </Button>
        </div>

        {preview && (
          <div
            className="space-y-3 rounded-lg border border-border bg-surface/40 p-4"
            data-testid="planet-mark-years-ocr-preview"
          >
            <p className="text-sm font-medium text-foreground">
              {t('planet_mark.shell.years.ocr.preview_title', {
                file: preview.source_filename,
              })}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('planet_mark.shell.years.ocr.method', {
                method: preview.extraction_method,
              })}
            </p>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {OCR_PREVIEW_FIELD_KEYS.map((key) => {
                const field = preview[key]
                const extracted = isExtractedField(field)
                return (
                  <div key={key} data-testid={`planet-mark-years-ocr-field-${key}`}>
                    <p className="text-xs text-muted-foreground">{t(ocrFieldLabelKey(key))}</p>
                    <p
                      className={
                        extracted
                          ? 'font-semibold text-foreground'
                          : 'font-medium text-muted-foreground'
                      }
                    >
                      {formatOcrFieldDisplay(field)}
                    </p>
                    {!extracted && (
                      <p className="text-xs text-muted-foreground">
                        {t('planet_mark.shell.years.ocr.not_extracted')}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>

            {preview.warnings.length > 0 && (
              <ul
                className="list-disc space-y-1 pl-5 text-xs text-muted-foreground"
                data-testid="planet-mark-years-ocr-warnings"
              >
                {preview.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}

            {preview.period_mismatch_warning && (
              <p
                className="text-sm text-warning"
                data-testid="planet-mark-years-ocr-period-mismatch"
                role="status"
              >
                {preview.period_mismatch_warning}
              </p>
            )}

            {preview.xlsx_ingested && (
              <div
                className="rounded-md border border-warning/30 bg-warning/5 p-3 text-sm"
                data-testid="planet-mark-years-ocr-xlsx-ssot"
              >
                <p className="text-foreground">{t('planet_mark.shell.years.ocr.xlsx_ssot_note')}</p>
                <label className="mt-2 flex items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={forceOverwrite}
                    onChange={(e) => setForceOverwrite(e.target.checked)}
                    data-testid="planet-mark-years-ocr-force-overwrite"
                  />
                  {t('planet_mark.shell.years.ocr.force_overwrite')}
                </label>
              </div>
            )}

            <Button
              type="button"
              disabled={!canApplyOcrPreview(preview) || applying}
              onClick={() => void runApply()}
              data-testid="planet-mark-years-ocr-apply"
            >
              {applying ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <CheckCircle2 className="h-4 w-4" aria-hidden />
              )}
              {t('planet_mark.shell.years.ocr.apply_cta')}
            </Button>
          </div>
        )}

        {applyResult && (
          <div
            className="rounded-md border border-success/30 bg-success/5 p-3 text-sm text-foreground"
            data-testid="planet-mark-years-ocr-apply-result"
          >
            {applyResult.message}
          </div>
        )}

        {error && (
          <div
            className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
            data-testid="planet-mark-years-ocr-error"
            role="alert"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div className="space-y-2">
              <p>{error}</p>
              {retryable && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void runScan()}
                  data-testid="planet-mark-years-ocr-retry"
                >
                  {t('common.retry', 'Retry')}
                </Button>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
