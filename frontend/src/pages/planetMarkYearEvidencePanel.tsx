import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Download, FileText, Loader2, RefreshCw, Upload } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import i18n from 'i18next'
import { getApiErrorMessage, planetMarkApi } from '../api/client'
import type { PlanetMarkEvidenceRecord } from '../api/planetMarkClient'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { cn } from '../helpers/utils'
import {
  PLANET_MARK_YEAR_CERT_DOC_TYPES,
  PLANET_MARK_YEAR_EVIDENCE_ACCEPT,
  buildYearEvidenceUploadFormData,
  evidenceHasStorageKey,
  filterYearReportEvidence,
  formatEvidenceFileSizeKb,
  formatEvidenceUploadedAt,
  isRetryableYearEvidenceError,
  validateYearEvidenceFile,
  yearEvidenceDocumentTypeLabelKey,
  type PlanetMarkYearCertDocType,
} from './planetMarkYearEvidenceHelpers'

type ListLoadState = 'idle' | 'loading' | 'success' | 'error'

interface UploadSlotState {
  uploading: boolean
  error: string | null
  retryable: boolean
  pendingFile: File | null
}

interface PlanetMarkYearEvidencePanelProps {
  yearId: number
  yearLabel: string
  /** Optional callback when the filtered evidence list refreshes (for OCR panel). */
  onEvidenceChange?: (evidence: PlanetMarkEvidenceRecord[]) => void
}

const UPLOAD_SLOTS: Array<{
  id: PlanetMarkYearCertDocType
  labelKey: string
  hintKey: string
  testId: string
}> = [
  {
    id: PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport,
    labelKey: 'planet_mark.shell.years.evidence.measurement_report',
    hintKey: 'planet_mark.shell.years.evidence.measurement_report_hint',
    testId: 'planet-mark-years-evidence-upload-measurement-report',
  },
  {
    id: PLANET_MARK_YEAR_CERT_DOC_TYPES.certificate,
    labelKey: 'planet_mark.shell.years.evidence.certificate',
    hintKey: 'planet_mark.shell.years.evidence.certificate_hint',
    testId: 'planet-mark-years-evidence-upload-certificate',
  },
]

function initialUploadSlots(): Record<PlanetMarkYearCertDocType, UploadSlotState> {
  return {
    [PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport]: {
      uploading: false,
      error: null,
      retryable: false,
      pendingFile: null,
    },
    [PLANET_MARK_YEAR_CERT_DOC_TYPES.certificate]: {
      uploading: false,
      error: null,
      retryable: false,
      pendingFile: null,
    },
  }
}

export function PlanetMarkYearEvidencePanel({
  yearId,
  yearLabel,
  onEvidenceChange,
}: PlanetMarkYearEvidencePanelProps) {
  const { t } = useTranslation()
  const [evidence, setEvidence] = useState<PlanetMarkEvidenceRecord[]>([])
  const [listState, setListState] = useState<ListLoadState>('idle')
  const [listError, setListError] = useState<string | null>(null)
  const [listRetryable, setListRetryable] = useState(false)
  const [uploadSlots, setUploadSlots] = useState(initialUploadSlots)
  const [downloadBusyId, setDownloadBusyId] = useState<number | null>(null)
  const fileInputRefs = useRef<Partial<Record<PlanetMarkYearCertDocType, HTMLInputElement | null>>>({})

  const loadEvidence = useCallback(async () => {
    setListState('loading')
    setListError(null)
    setListRetryable(false)
    try {
      const response = await planetMarkApi.listEvidence(yearId)
      const filtered = filterYearReportEvidence(response.data.evidence ?? [])
      setEvidence(filtered)
      onEvidenceChange?.(filtered)
      setListState('success')
    } catch (err: unknown) {
      setListState('error')
      setListError(
        getApiErrorMessage(err, i18n.t('planet_mark.shell.years.evidence.list_error')),
      )
      setListRetryable(isRetryableYearEvidenceError(err))
    }
  }, [yearId, onEvidenceChange])

  useEffect(() => {
    void loadEvidence()
  }, [loadEvidence])

  const setSlotState = (
    documentType: PlanetMarkYearCertDocType,
    patch: Partial<UploadSlotState>,
  ) => {
    setUploadSlots((current) => ({
      ...current,
      [documentType]: { ...current[documentType], ...patch },
    }))
  }

  const uploadFile = async (documentType: PlanetMarkYearCertDocType, file: File) => {
    const validationError = validateYearEvidenceFile(file)
    if (validationError) {
      setSlotState(documentType, {
        uploading: false,
        error: validationError,
        retryable: false,
        pendingFile: null,
      })
      return
    }

    setSlotState(documentType, {
      uploading: true,
      error: null,
      retryable: false,
      pendingFile: file,
    })

    try {
      await planetMarkApi.uploadEvidence(yearId, buildYearEvidenceUploadFormData(file, documentType))
      setSlotState(documentType, {
        uploading: false,
        error: null,
        retryable: false,
        pendingFile: null,
      })
      const input = fileInputRefs.current[documentType]
      if (input) input.value = ''
      await loadEvidence()
    } catch (err: unknown) {
      setSlotState(documentType, {
        uploading: false,
        error: getApiErrorMessage(err, i18n.t('planet_mark.shell.years.evidence.upload_error')),
        retryable: isRetryableYearEvidenceError(err),
        pendingFile: file,
      })
    }
  }

  const handleFileSelected = (documentType: PlanetMarkYearCertDocType, file: File | undefined) => {
    if (!file) return
    void uploadFile(documentType, file)
  }

  const retryUpload = (documentType: PlanetMarkYearCertDocType) => {
    const pendingFile = uploadSlots[documentType].pendingFile
    if (!pendingFile) return
    void uploadFile(documentType, pendingFile)
  }

  const downloadEvidence = async (item: PlanetMarkEvidenceRecord) => {
    if (!evidenceHasStorageKey(item.storage_key)) return
    setDownloadBusyId(item.id)
    try {
      const response = await planetMarkApi.getEvidenceDownloadUrl(yearId, item.id)
      const url = response.data.url
      if (url) window.open(url, '_blank', 'noopener,noreferrer')
    } catch (err: unknown) {
      setListError(
        getApiErrorMessage(err, i18n.t('planet_mark.shell.years.evidence.download_error')),
      )
    } finally {
      setDownloadBusyId(null)
    }
  }

  const sortedEvidence = [...evidence].sort(
    (left, right) => new Date(right.uploaded_at).getTime() - new Date(left.uploaded_at).getTime(),
  )

  const hasCertificate = evidence.some(
    (item) =>
      item.document_type === PLANET_MARK_YEAR_CERT_DOC_TYPES.certificate &&
      evidenceHasStorageKey(item.storage_key),
  )
  const hasMeasurement = evidence.some(
    (item) =>
      item.document_type === PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport &&
      evidenceHasStorageKey(item.storage_key),
  )

  return (
    <Card data-testid="planet-mark-years-evidence-panel">
      <CardHeader>
        <CardTitle>{t('planet_mark.shell.years.evidence.title')}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {t('planet_mark.shell.years.evidence.hint', { year: yearLabel })}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          {UPLOAD_SLOTS.map((slot) => {
            const slotState = uploadSlots[slot.id]
            return (
              <div
                key={slot.id}
                className="rounded-lg border border-border bg-surface/30 p-4"
                data-testid={slot.testId}
              >
                <div className="mb-3">
                  <p className="font-medium text-foreground">{t(slot.labelKey)}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{t(slot.hintKey)}</p>
                </div>

                {slotState.uploading ? (
                  <div
                    className="flex items-center gap-2 rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground"
                    data-testid={`${slot.testId}-uploading`}
                  >
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                    {t('planet_mark.shell.years.evidence.uploading')}
                  </div>
                ) : (
                  <button
                    type="button"
                    className={cn(
                      'w-full rounded-md border-2 border-dashed p-4 text-center transition-colors',
                      slotState.error
                        ? 'border-destructive/40 bg-destructive/5'
                        : 'border-border hover:border-primary/40 hover:bg-primary/5',
                    )}
                    onClick={() => fileInputRefs.current[slot.id]?.click()}
                    data-testid={`${slot.testId}-picker`}
                  >
                    <Upload className="mx-auto mb-2 h-5 w-5 text-muted-foreground" aria-hidden />
                    <p className="text-sm text-muted-foreground">
                      {t('planet_mark.shell.years.evidence.pick_file')}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t('planet_mark.shell.years.evidence.file_types_hint')}
                    </p>
                  </button>
                )}

                {slotState.error && (
                  <div
                    className="mt-3 flex flex-col gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 sm:flex-row sm:items-center sm:justify-between"
                    data-testid={`${slot.testId}-error`}
                    role="alert"
                  >
                    <p className="text-sm text-destructive">{slotState.error}</p>
                    {slotState.retryable && slotState.pendingFile && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => retryUpload(slot.id)}
                        data-testid={`${slot.testId}-retry`}
                      >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        {t('common.retry', 'Retry')}
                      </Button>
                    )}
                  </div>
                )}

                <input
                  ref={(node) => {
                    fileInputRefs.current[slot.id] = node
                  }}
                  type="file"
                  accept={PLANET_MARK_YEAR_EVIDENCE_ACCEPT}
                  className="hidden"
                  onChange={(event) => handleFileSelected(slot.id, event.target.files?.[0])}
                  data-testid={`${slot.testId}-input`}
                />
              </div>
            )
          })}
        </div>

        {listState === 'success' && (
          <div
            className="flex flex-wrap gap-3 text-xs text-muted-foreground"
            data-testid="planet-mark-years-evidence-status"
          >
            <span data-testid="planet-mark-years-evidence-measurement-status">
              {hasMeasurement
                ? t('planet_mark.shell.years.evidence.status.measurement_ok')
                : t('planet_mark.shell.years.evidence.status.measurement_missing')}
            </span>
            <span data-testid="planet-mark-years-evidence-certificate-status">
              {hasCertificate
                ? t('planet_mark.shell.years.evidence.status.certificate_ok')
                : t('planet_mark.shell.years.evidence.status.certificate_missing')}
            </span>
          </div>
        )}

        <div data-testid="planet-mark-years-evidence-list">
          <p className="mb-3 text-sm font-medium text-foreground">
            {t('planet_mark.shell.years.evidence.list_title')}
          </p>

          {listState === 'loading' && (
            <div
              className="flex items-center gap-2 py-6 text-sm text-muted-foreground justify-center"
              data-testid="planet-mark-years-evidence-list-loading"
            >
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              {t('planet_mark.shell.years.evidence.list_loading')}
            </div>
          )}

          {listState === 'error' && (
            <div
              className="flex flex-col gap-3 rounded-lg border border-warning/30 bg-warning/5 p-4 sm:flex-row sm:items-start sm:justify-between"
              data-testid="planet-mark-years-evidence-list-error"
            >
              <div className="flex gap-3">
                <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" aria-hidden />
                <div>
                  <p className="font-medium text-foreground">
                    {t('planet_mark.shell.years.evidence.list_unavailable')}
                  </p>
                  <p className="mt-1 text-sm text-warning">{listError}</p>
                </div>
              </div>
              {listRetryable && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void loadEvidence()}
                  data-testid="planet-mark-years-evidence-list-retry"
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {t('common.retry', 'Retry')}
                </Button>
              )}
            </div>
          )}

          {listState === 'success' && sortedEvidence.length === 0 && (
            <div data-testid="planet-mark-years-evidence-list-empty">
              <EmptyState
                title={t('planet_mark.shell.years.evidence.empty_title')}
                description={t('planet_mark.shell.years.evidence.empty_desc')}
              />
            </div>
          )}

          {listState === 'success' && sortedEvidence.length > 0 && (
            <div className="divide-y divide-border rounded-lg border border-border">
              {sortedEvidence.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                  data-testid={`planet-mark-years-evidence-row-${item.id}`}
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <FileText className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" aria-hidden />
                    <div className="min-w-0">
                      <p className="font-medium text-foreground truncate">{item.document_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {t(yearEvidenceDocumentTypeLabelKey(item.document_type))}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-col items-stretch gap-2 sm:items-end">
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground sm:text-right">
                      <span data-testid={`planet-mark-years-evidence-size-${item.id}`}>
                        {formatEvidenceFileSizeKb(item.file_size_kb)}
                      </span>
                      <span data-testid={`planet-mark-years-evidence-uploaded-${item.id}`}>
                        {formatEvidenceUploadedAt(item.uploaded_at)}
                      </span>
                    </div>
                    {evidenceHasStorageKey(item.storage_key) ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={downloadBusyId === item.id}
                        onClick={() => void downloadEvidence(item)}
                        data-testid={`planet-mark-years-evidence-download-${item.id}`}
                      >
                        {downloadBusyId === item.id ? (
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" aria-hidden />
                        ) : (
                          <Download className="mr-2 h-3.5 w-3.5" aria-hidden />
                        )}
                        {t('planet_mark.shell.years.evidence.download')}
                      </Button>
                    ) : (
                      <p
                        className="text-xs text-destructive"
                        data-testid={`planet-mark-years-evidence-storage-missing-${item.id}`}
                      >
                        {t('planet_mark.shell.years.evidence.storage_missing')}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
