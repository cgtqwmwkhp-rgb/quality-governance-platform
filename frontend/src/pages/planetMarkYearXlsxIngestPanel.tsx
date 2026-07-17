import { useRef, useState } from 'react'
import { AlertTriangle, Loader2, RefreshCw, Upload } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import i18n from 'i18next'
import { getApiErrorMessage, planetMarkApi } from '../api/client'
import type { PlanetMarkMsXlsxIngestResponse } from '../api/planetMarkClient'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import {
  PLANET_MARK_MS_XLSX_ACCEPT,
  buildMsXlsxIngestFormData,
  formatIngestedTotals,
  isRetryableMsXlsxIngestError,
  validateMsXlsxFile,
  yearLabelMatchesWorkbook,
} from './planetMarkYearXlsxIngestHelpers'

interface PlanetMarkYearXlsxIngestPanelProps {
  yearId: number
  yearLabel: string
  hasIngestedCarbon: boolean
  currentTotal: number | null
  currentPerFte: number | null
  onIngested: () => void | Promise<void>
}

export function PlanetMarkYearXlsxIngestPanel({
  yearId,
  yearLabel,
  hasIngestedCarbon,
  currentTotal,
  currentPerFte,
  onIngested,
}: PlanetMarkYearXlsxIngestPanelProps) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retryable, setRetryable] = useState(false)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [lastResult, setLastResult] = useState<PlanetMarkMsXlsxIngestResponse | null>(null)

  const uploadFile = async (file: File) => {
    const validationError = validateMsXlsxFile(file)
    if (validationError) {
      setError(validationError)
      setRetryable(false)
      setPendingFile(null)
      return
    }

    const yearMatch = yearLabelMatchesWorkbook(yearLabel, file.name)
    if (!yearMatch.ok) {
      setError(
        t('planet_mark.shell.years.ingest_year_mismatch', {
          workbook: yearMatch.workbookYear,
          year: yearLabel,
        }),
      )
      setRetryable(false)
      setPendingFile(null)
      return
    }

    setUploading(true)
    setError(null)
    setRetryable(false)
    setPendingFile(file)

    try {
      const response = await planetMarkApi.ingestMsXlsx(yearId, buildMsXlsxIngestFormData(file))
      setLastResult(response.data)
      setPendingFile(null)
      if (inputRef.current) inputRef.current.value = ''
      await onIngested()
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, i18n.t('planet_mark.shell.years.ingest_error')))
      setRetryable(isRetryableMsXlsxIngestError(err))
    } finally {
      setUploading(false)
    }
  }

  const formatted =
    lastResult != null
      ? formatIngestedTotals(lastResult)
      : hasIngestedCarbon && currentTotal != null
        ? {
            total: currentTotal.toFixed(1),
            perFte: currentPerFte != null ? currentPerFte.toFixed(2) : '—',
            scope1: '—',
            scope2: '—',
            scope3: '—',
          }
        : null

  return (
    <Card data-testid="planet-mark-years-xlsx-ingest">
      <CardHeader>
        <CardTitle>{t('planet_mark.shell.years.ingest_title')}</CardTitle>
        <p className="text-sm text-muted-foreground">{t('planet_mark.shell.years.ingest_hint')}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {formatted ? (
          <div
            className="rounded-lg border border-border bg-surface/50 p-4 space-y-2"
            data-testid="planet-mark-years-xlsx-ingest-totals"
          >
            <p className="text-sm font-medium text-foreground">
              {t('planet_mark.shell.years.ingest_success_title', { year: yearLabel })}
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">{t('planet_mark.tco2e_total')}</p>
                <p className="font-semibold text-foreground">{formatted.total}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{t('planet_mark.tco2e_fte')}</p>
                <p className="font-semibold text-foreground">{formatted.perFte}</p>
              </div>
              {lastResult && (
                <>
                  <div>
                    <p className="text-xs text-muted-foreground">
                      {t('planet_mark.shell.years.ingest_scope_1')}
                    </p>
                    <p className="font-semibold text-foreground">{formatted.scope1}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">
                      {t('planet_mark.shell.years.ingest_scope_3')}
                    </p>
                    <p className="font-semibold text-foreground">{formatted.scope3}</p>
                  </div>
                </>
              )}
            </div>
            {lastResult?.source_filename && (
              <p className="text-xs text-muted-foreground">
                {t('planet_mark.shell.years.ingest_from_file', {
                  file: lastResult.source_filename,
                })}
              </p>
            )}
          </div>
        ) : (
          <EmptyState
            title={t('planet_mark.shell.years.ingest_empty')}
            description={t('planet_mark.shell.years.ingest_empty_desc')}
          />
        )}

        <input
          ref={inputRef}
          type="file"
          accept={PLANET_MARK_MS_XLSX_ACCEPT}
          className="sr-only"
          data-testid="planet-mark-years-xlsx-ingest-input"
          aria-label={t('planet_mark.shell.years.ingest_cta')}
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void uploadFile(file)
          }}
        />

        {uploading ? (
          <div
            className="flex items-center gap-2 rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground"
            data-testid="planet-mark-years-xlsx-ingest-uploading"
          >
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            {t('planet_mark.shell.years.ingest_uploading')}
          </div>
        ) : (
          <Button
            variant="outline"
            data-testid="planet-mark-years-xlsx-ingest-button"
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="w-4 h-4" />
            {t('planet_mark.shell.years.ingest_cta')}
          </Button>
        )}

        {error && (
          <div
            className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
            data-testid="planet-mark-years-xlsx-ingest-error"
            role="alert"
          >
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden />
            <div className="space-y-2">
              <p>{error}</p>
              {retryable && pendingFile && (
                <Button
                  size="sm"
                  variant="outline"
                  data-testid="planet-mark-years-xlsx-ingest-retry"
                  onClick={() => void uploadFile(pendingFile)}
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  {t('planet_mark.shell.years.ingest_retry')}
                </Button>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
