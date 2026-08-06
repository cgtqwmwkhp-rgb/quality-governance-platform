import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import {
  complianceScheduleApi,
  evidenceAssetsApi,
  getApiErrorMessage,
  type EvidenceAsset,
} from '../../api/client'
import type { ComplianceRecord } from '../../api/complianceScheduleClient'
import { toast } from '../../contexts/ToastContext'
import { useTaxonomyOptions } from './useTaxonomyOptions'

const SELECT_CLASS =
  'w-full appearance-none rounded-lg border border-border bg-background px-3 py-2 text-sm ' +
  'text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50'

/**
 * File one occurrence's evidence into the Governance Library.
 *
 * ADR-0020 keeps this a step of its own. Completing an occurrence records that
 * the work happened; it puts nothing in the Library, so this control exists to
 * make the second step something a user has to choose. The state line is shown
 * whether or not anything has been filed, because "complete but not filed" is a
 * real and common position and hiding it would read as "filed".
 */
export function RecordFilingControl({
  record,
  onFiled,
}: {
  record: ComplianceRecord
  onFiled: () => void
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [assets, setAssets] = useState<EvidenceAsset[] | null>(null)
  const [assetsFailed, setAssetsFailed] = useState(false)
  const [assetId, setAssetId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [title, setTitle] = useState('')

  const taxonomy = useTaxonomyOptions(open)
  const filingCategories = useMemo(
    // A category with no id cannot be addressed by the filing endpoint, so it
    // is dropped rather than offered as a choice that would 422 on submit.
    () => taxonomy.options.filter((option) => option.id != null),
    [taxonomy.options],
  )

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setAssetsFailed(false)
    void (async () => {
      try {
        const response = await evidenceAssetsApi.list({
          source_module: 'compliance_record',
          source_id: record.id,
          page_size: 50,
        })
        if (!cancelled) setAssets(response.data.items ?? [])
      } catch {
        if (cancelled) return
        // Left null rather than empty: "we could not read the list" and "there
        // is nothing attached" call for different actions from the user.
        setAssets(null)
        setAssetsFailed(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, record.id])

  const submit = useCallback(async () => {
    if (!assetId || !categoryId) return
    setBusy(true)
    try {
      const response = await complianceScheduleApi.fileRecordToLibrary(record.id, {
        evidence_asset_id: Number(assetId),
        category_id: Number(categoryId),
        ...(title.trim() ? { title: title.trim() } : {}),
      })
      const ref = response.data.pel_doc_ref
      toast.success(
        ref
          ? t('compliance.schedule.filing.success_ref', 'Filed to the Library as {{ref}}', { ref })
          : t('compliance.schedule.filing.success', 'Filed to the Library'),
      )
      if (response.data.duplicate_warning) {
        // The filing still succeeded — this is a prompt to go and look, not a
        // failure, so it must not be reported as one.
        toast.warning(
          t(
            'compliance.schedule.filing.duplicate_warning',
            'The Library already holds an approved document that looks like this one. Check before relying on it.',
          ),
        )
      }
      setOpen(false)
      setAssetId('')
      setCategoryId('')
      setTitle('')
      onFiled()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
      // Refresh regardless: a storage failure marks the occurrence
      // ``filing_failed`` server-side, and the row should show that.
      onFiled()
    } finally {
      setBusy(false)
    }
  }, [assetId, categoryId, title, record.id, onFiled, t])

  const testId = `compliance-schedule-record-filing-${record.id}`

  return (
    <div className="mt-2 text-xs" data-testid={testId}>
      <div className="flex flex-wrap items-center gap-2">
        <FilingStatusLine record={record} />
        {record.filing_status !== 'filed' && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto px-0 text-xs text-muted-foreground hover:text-foreground"
            aria-expanded={open}
            data-testid={`${testId}-toggle`}
            onClick={() => setOpen((v) => !v)}
          >
            {open
              ? t('common.cancel', 'Cancel')
              : record.filing_status === 'filing_failed'
                ? t('compliance.schedule.filing.retry_cta', 'Try filing again')
                : t('compliance.schedule.filing.cta', 'File to Library')}
          </Button>
        )}
      </div>

      {open && (
        <div className="mt-2 space-y-2 rounded-lg border border-border bg-background p-3">
          <p className="text-muted-foreground">
            {t(
              'compliance.schedule.filing.explainer',
              'Filing copies the evidence into the Governance Library as a draft under the category you choose. It does not approve or publish it.',
            )}
          </p>

          <label className="block space-y-1">
            <span className="text-muted-foreground">
              {t('compliance.schedule.filing.evidence_label', 'Evidence to file')}
            </span>
            <select
              className={SELECT_CLASS}
              value={assetId}
              disabled={busy}
              data-testid={`${testId}-evidence-select`}
              onChange={(e) => setAssetId(e.target.value)}
            >
              <option value="">
                {t('compliance.schedule.filing.evidence_placeholder', 'Choose an attachment')}
              </option>
              {(assets ?? []).map((asset) => (
                <option key={asset.id} value={String(asset.id)}>
                  {asset.title || asset.original_filename || `#${asset.id}`}
                </option>
              ))}
            </select>
          </label>

          {assetsFailed && (
            <p className="text-amber-600" data-testid={`${testId}-evidence-failed`}>
              {t(
                'compliance.schedule.filing.evidence_failed',
                'The attachments for this occurrence could not be read, so there is nothing to choose from yet.',
              )}
            </p>
          )}
          {!assetsFailed && assets !== null && assets.length === 0 && (
            <p className="text-muted-foreground" data-testid={`${testId}-evidence-empty`}>
              {t(
                'compliance.schedule.filing.evidence_empty',
                'Nothing is attached to this occurrence yet. Upload the evidence above first, then file it.',
              )}
            </p>
          )}

          <label className="block space-y-1">
            <span className="text-muted-foreground">
              {t('compliance.schedule.filing.category_label', 'Library category')}
            </span>
            <select
              className={SELECT_CLASS}
              value={categoryId}
              disabled={busy || taxonomy.loading || taxonomy.failed}
              data-testid={`${testId}-category-select`}
              onChange={(e) => setCategoryId(e.target.value)}
            >
              <option value="">
                {taxonomy.loading
                  ? t('common.loading', 'Loading…')
                  : t('compliance.schedule.filing.category_placeholder', 'Choose a category')}
              </option>
              {filingCategories.map((option) => (
                <option key={option.id} value={String(option.id)}>
                  {option.taxonomyId} — {option.name}
                </option>
              ))}
            </select>
          </label>

          {taxonomy.failed && (
            <p className="text-amber-600" data-testid={`${testId}-category-failed`}>
              {t(
                'compliance.schedule.filing.category_failed',
                'The Library category list could not be loaded, so nothing can be filed yet.',
              )}
            </p>
          )}

          <label className="block space-y-1">
            <span className="text-muted-foreground">
              {t('compliance.schedule.filing.title_label', 'Library title (optional)')}
            </span>
            <Input
              value={title}
              disabled={busy}
              data-testid={`${testId}-title-input`}
              placeholder={t(
                'compliance.schedule.filing.title_placeholder',
                'Defaults to the attachment name',
              )}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>

          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              disabled={busy || !assetId || !categoryId}
              data-testid={`${testId}-submit`}
              onClick={() => void submit()}
            >
              {busy
                ? t('common.saving', 'Saving…')
                : t('compliance.schedule.filing.submit', 'File to Library')}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function FilingStatusLine({ record }: { record: ComplianceRecord }) {
  const { t } = useTranslation()

  if (record.filing_status === 'filed' && record.library_document_id != null) {
    return (
      <span
        className="text-muted-foreground"
        data-testid={`compliance-schedule-record-filed-${record.id}`}
      >
        {t('compliance.schedule.filing.filed', 'Filed to Library')}{' '}
        <Link className="underline" to={`/documents/${record.library_document_id}`}>
          {t('compliance.schedule.filing.open_document', 'Open document')}
        </Link>
      </span>
    )
  }

  if (record.filing_status === 'filing_failed') {
    return (
      <span
        className="text-amber-600"
        data-testid={`compliance-schedule-record-filing-failed-${record.id}`}
      >
        {t('compliance.schedule.filing.failed', 'Filing failed')}
        {record.filing_error ? ` — ${record.filing_error}` : ''}
      </span>
    )
  }

  return (
    <span
      className="text-muted-foreground"
      data-testid={`compliance-schedule-record-not-filed-${record.id}`}
    >
      {t('compliance.schedule.filing.not_filed', 'Not filed to Library')}
    </span>
  )
}
