import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import axios from 'axios'
import { CaseEvidencePanel } from '../../components/case/CaseEvidencePanel'
import { Button } from '../../components/ui/Button'
import {
  complianceScheduleFraOcrApi,
  evidenceAssetsApi,
  getApiErrorMessage,
} from '../../api/client'
import type { FraOcrDraftResponse } from '../../api/complianceScheduleFraOcrClient'
import { toast } from '../../contexts/ToastContext'
import { useFeatureFlag } from '../../hooks/useFeatureFlag'

function isPdfAsset(asset: {
  content_type?: string
  original_filename?: string | null
  title?: string | null
}): boolean {
  if (asset.content_type === 'application/pdf') return true
  const name = (asset.original_filename || asset.title || '').toLowerCase()
  return name.endsWith('.pdf')
}

/**
 * Evidence for one Compliance Schedule occurrence.
 *
 * The evidence-assets API validates `source_module=compliance_record` against
 * ``ComplianceRecord`` (a completion or miss), not against the obligation. So
 * upload lives here — per occurrence — rather than once on the detail page.
 * Collapsed by default so a long history does not fire one list request per row;
 * a visible upload CTA opens the panel without requiring the muted toggle.
 *
 * When the FRA OCR flag is on and the obligation is ``fra_ocr_eligible``, a PDF
 * upload also creates a pending FRA OCR draft from the evidence blob (no second
 * file picker). Obligation-level ``FraOcrUploadControl`` remains available.
 */
export function RecordEvidenceSection({
  recordId,
  referenceNumber,
  enableUpload = true,
  fraOcrEligible = false,
  onFraOcrDraftCreated,
}: {
  recordId: number
  referenceNumber: string
  enableUpload?: boolean
  /** Server ``fra_ocr_eligible`` for the parent obligation. */
  fraOcrEligible?: boolean
  onFraOcrDraftCreated?: (draft: FraOcrDraftResponse) => void
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const fraOcrEnabled = useFeatureFlag('compliance_schedule_fra_ocr')

  const handleUploadComplete = useCallback(
    async (result?: { uploadedAssetIds: number[] }) => {
      const uploadedIds = result?.uploadedAssetIds ?? []
      if (!fraOcrEnabled || !fraOcrEligible || uploadedIds.length === 0) return

      let pdfAssetIds: number[] = []
      try {
        const listed = await evidenceAssetsApi.list({
          source_module: 'compliance_record',
          source_id: recordId,
          page_size: 50,
        })
        const items = listed.data.items ?? []
        pdfAssetIds = items
          .filter((asset) => uploadedIds.includes(asset.id) && isPdfAsset(asset))
          .map((asset) => asset.id)
      } catch {
        // Fall back to attempting every uploaded id; backend refuses non-PDFs.
        pdfAssetIds = uploadedIds
      }

      for (const evidenceAssetId of pdfAssetIds) {
        try {
          const response = await complianceScheduleFraOcrApi.createDraftFromEvidence(recordId, {
            evidence_asset_id: evidenceAssetId,
          })
          toast.success(
            t(
              'compliance.schedule.fra_ocr.from_evidence.success',
              'FRA draft ready for review from the uploaded PDF.',
            ),
          )
          onFraOcrDraftCreated?.(response.data)
        } catch (err) {
          const status = axios.isAxiosError(err) ? err.response?.status : undefined
          if (status === 409) {
            toast.info(
              getApiErrorMessage(
                err,
                t(
                  'compliance.schedule.fra_ocr.from_evidence.duplicate',
                  'A pending FRA draft already exists for this PDF on this obligation — open it from the FRA ingest panel.',
                ),
              ),
            )
            continue
          }
          if (status === 404) {
            // Flag/module closed, or asset not bound — silent for auto-trigger.
            continue
          }
          if (status === 400 || status === 422) {
            // Non-PDF / oversize / checksum — upload itself succeeded; do not
            // paint the occurrence upload red for an OCR gate refusal.
            continue
          }
          toast.error(
            getApiErrorMessage(
              err,
              t(
                'compliance.schedule.fra_ocr.from_evidence.error',
                'The PDF was uploaded, but FRA OCR could not start. Try again from the FRA ingest panel.',
              ),
            ),
          )
        }
      }
    },
    [fraOcrEnabled, fraOcrEligible, recordId, onFraOcrDraftCreated, t],
  )

  return (
    <div className="mt-2 space-y-2" data-testid={`compliance-schedule-record-evidence-${recordId}`}>
      <div className="flex flex-wrap items-center gap-2">
        {enableUpload ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8"
            data-testid={`compliance-schedule-record-evidence-upload-cta-${recordId}`}
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            {t(
              'compliance.schedule.evidence.upload_cta',
              'Upload documents for this past occurrence',
            )}
          </Button>
        ) : null}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-auto px-0 text-xs text-muted-foreground hover:text-foreground"
          data-testid={`compliance-schedule-record-evidence-toggle-${recordId}`}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open
            ? t('compliance.schedule.evidence.hide', 'Hide evidence')
            : t('compliance.schedule.evidence.show', 'Evidence for this occurrence')}
        </Button>
      </div>
      {open && (
        <div className="mt-2">
          <CaseEvidencePanel
            sourceType="compliance_record"
            sourceId={recordId}
            enableUpload={enableUpload}
            testIdPrefix={`compliance-record-${recordId}`}
            title={t('compliance.schedule.evidence.title', 'Occurrence evidence')}
            emptyTitle={t(
              'compliance.schedule.evidence.empty_title',
              'No evidence on this occurrence yet',
            )}
            emptyDescription={t(
              'compliance.schedule.evidence.empty_description',
              'Upload certificates, reports, or photos that prove {{ref}} was done.',
              { ref: referenceNumber },
            )}
            onUploadComplete={handleUploadComplete}
          />
        </div>
      )}
    </div>
  )
}
