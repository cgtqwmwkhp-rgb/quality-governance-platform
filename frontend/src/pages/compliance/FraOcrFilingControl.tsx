import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { complianceScheduleFraOcrApi, getApiErrorMessage } from '../../api/client'
import type { FraOcrDraftResponse } from '../../api/complianceScheduleFraOcrClient'
import { toast } from '../../contexts/ToastContext'
import { FRA_TAXONOMY_ID } from './fraOcrHelpers'
import { useTaxonomyOptions } from './useTaxonomyOptions'

const SELECT_CLASS =
  'w-full appearance-none rounded-lg border border-border bg-background px-3 py-2 text-sm ' +
  'text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50'

interface FraOcrFilingControlProps {
  draft: FraOcrDraftResponse
  onFiled: (draft: FraOcrDraftResponse) => void
}

/**
 * File a confirmed FRA OCR source PDF into the Governance Library under
 * taxonomy 03.01 only. Completing/confirming the draft does not file it.
 */
export function FraOcrFilingControl({ draft, onFiled }: FraOcrFilingControlProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [categoryId, setCategoryId] = useState('')
  const [title, setTitle] = useState('')

  const taxonomy = useTaxonomyOptions(open)
  const filingCategories = useMemo(
    () =>
      taxonomy.options.filter(
        (option) => option.id != null && option.taxonomyId === FRA_TAXONOMY_ID,
      ),
    [taxonomy.options],
  )

  const canFile =
    draft.status === 'confirmed' &&
    (draft.filing_status === 'not_filed' || draft.filing_status === 'filing_failed')

  const submit = useCallback(async () => {
    if (!categoryId || !canFile) return
    setBusy(true)
    try {
      const response = await complianceScheduleFraOcrApi.fileDraft(draft.id, {
        category_id: Number(categoryId),
        ...(title.trim() ? { title: title.trim() } : {}),
      })
      const ref = response.data.pel_doc_ref
      toast.success(
        ref
          ? t('compliance.schedule.fra_ocr.filing.success_ref', 'Filed to the Library as {{ref}}', {
              ref,
            })
          : t('compliance.schedule.fra_ocr.filing.success', 'Filed to the Library'),
      )
      if (response.data.duplicate_warning) {
        toast.warning(
          t(
            'compliance.schedule.fra_ocr.filing.duplicate_warning',
            'The Library already holds an approved document that looks like this one. Check before relying on it.',
          ),
        )
      }
      setOpen(false)
      setCategoryId('')
      setTitle('')
      onFiled(response.data.draft)
    } catch (err) {
      toast.error(getApiErrorMessage(err))
      onFiled(draft)
    } finally {
      setBusy(false)
    }
  }, [categoryId, canFile, draft, title, onFiled, t])

  if (draft.status !== 'confirmed') return null

  const testId = `fra-ocr-filing-${draft.id}`

  return (
    <div className="mt-2 text-xs" data-testid={testId}>
      <div className="flex flex-wrap items-center gap-2">
        <FilingStatusLine draft={draft} />
        {canFile && (
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
              : draft.filing_status === 'filing_failed'
                ? t('compliance.schedule.fra_ocr.filing.retry_cta', 'Try filing again')
                : t('compliance.schedule.fra_ocr.filing.cta', 'File to Library')}
          </Button>
        )}
      </div>

      {open && canFile && (
        <div className="mt-2 space-y-2 rounded-lg border border-border bg-background p-3">
          <p className="text-muted-foreground">
            {t(
              'compliance.schedule.fra_ocr.filing.explainer',
              'Filing copies the FRA PDF into the Governance Library as a draft under Fire Risk Assessment (03.01). It does not approve or publish it.',
            )}
          </p>

          <label className="block space-y-1">
            <span className="text-muted-foreground">
              {t('compliance.schedule.fra_ocr.filing.category_label', 'Library category')}
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
                  : t('compliance.schedule.fra_ocr.filing.category_placeholder', 'Choose a category')}
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
                'compliance.schedule.fra_ocr.filing.category_failed',
                'The Library category list could not be loaded, so nothing can be filed yet.',
              )}
            </p>
          )}

          <label className="block space-y-1">
            <span className="text-muted-foreground">
              {t('compliance.schedule.fra_ocr.filing.title_label', 'Library title (optional)')}
            </span>
            <Input
              value={title}
              disabled={busy}
              data-testid={`${testId}-title-input`}
              placeholder={t(
                'compliance.schedule.fra_ocr.filing.title_placeholder',
                'Defaults to the source filename',
              )}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>

          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              disabled={busy || !categoryId}
              data-testid={`${testId}-submit`}
              onClick={() => void submit()}
            >
              {busy
                ? t('common.saving', 'Saving…')
                : t('compliance.schedule.fra_ocr.filing.submit', 'File to Library')}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function FilingStatusLine({ draft }: { draft: FraOcrDraftResponse }) {
  const { t } = useTranslation()

  if (draft.filing_status === 'filed' && draft.library_document_id != null) {
    return (
      <span className="text-muted-foreground" data-testid={`fra-ocr-filed-${draft.id}`}>
        {t('compliance.schedule.fra_ocr.filing.filed', 'Filed to Library')}{' '}
        <Link className="underline" to={`/documents/${draft.library_document_id}`}>
          {t('compliance.schedule.fra_ocr.filing.open_document', 'Open document')}
        </Link>
      </span>
    )
  }

  if (draft.filing_status === 'filing_failed') {
    return (
      <span className="text-amber-600" data-testid={`fra-ocr-filing-failed-${draft.id}`}>
        {t('compliance.schedule.fra_ocr.filing.failed', 'Filing failed')}
        {draft.filing_error ? ` — ${draft.filing_error}` : ''}
      </span>
    )
  }

  return (
    <span className="text-muted-foreground" data-testid={`fra-ocr-not-filed-${draft.id}`}>
      {t('compliance.schedule.fra_ocr.filing.not_filed', 'Not filed to Library')}
    </span>
  )
}
