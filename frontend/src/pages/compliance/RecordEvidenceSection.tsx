import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CaseEvidencePanel } from '../../components/case/CaseEvidencePanel'
import { Button } from '../../components/ui/Button'

/**
 * Evidence for one Compliance Schedule occurrence.
 *
 * The evidence-assets API validates `source_module=compliance_record` against
 * ``ComplianceRecord`` (a completion or miss), not against the obligation. So
 * upload lives here — per occurrence — rather than once on the detail page.
 * Collapsed by default so a long history does not fire one list request per row;
 * a visible upload CTA opens the panel without requiring the muted toggle.
 */
export function RecordEvidenceSection({
  recordId,
  referenceNumber,
  enableUpload = true,
}: {
  recordId: number
  referenceNumber: string
  enableUpload?: boolean
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

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
          />
        </div>
      )}
    </div>
  )
}
