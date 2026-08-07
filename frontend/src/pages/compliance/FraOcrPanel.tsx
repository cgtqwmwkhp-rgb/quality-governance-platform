import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/Button'
import { complianceScheduleFraOcrApi, getApiErrorMessage } from '../../api/client'
import type { FraOcrDraftResponse } from '../../api/complianceScheduleFraOcrClient'
import type { ComplianceRequirement } from '../../api/complianceScheduleClient'
import { toast } from '../../contexts/ToastContext'
import { useFeatureFlag } from '../../hooks/useFeatureFlag'
import { FraOcrFilingControl } from './FraOcrFilingControl'
import { FraOcrReviewSheet } from './FraOcrReviewSheet'
import { FraOcrUploadControl } from './FraOcrUploadControl'
import { isFraOcrEligible } from './fraOcrHelpers'

interface FraOcrPanelProps {
  requirement: ComplianceRequirement
  onRequirementUpdated: (requirement: ComplianceRequirement) => void
}

/**
 * Obligation-detail Ingest panel for site-scoped FRA (03.01) when the FRA OCR
 * feature flag is on. Hidden otherwise — no empty chrome for ineligible rows.
 */
export function FraOcrPanel({ requirement, onRequirementUpdated }: FraOcrPanelProps) {
  const { t } = useTranslation()
  const enabled = useFeatureFlag('compliance_schedule_fra_ocr')
  const eligible = isFraOcrEligible(requirement)

  const [drafts, setDrafts] = useState<FraOcrDraftResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [reviewDraft, setReviewDraft] = useState<FraOcrDraftResponse | null>(null)
  const [reviewOpen, setReviewOpen] = useState(false)

  const loadDrafts = useCallback(async () => {
    if (!enabled || !eligible) return
    setLoading(true)
    try {
      const response = await complianceScheduleFraOcrApi.listDrafts(requirement.id, {
        page_size: 50,
      })
      const visible = (response.data.items ?? []).filter(
        (d) => d.status === 'pending' || d.status === 'confirmed',
      )
      setDrafts(visible)
    } catch (err) {
      toast.error(getApiErrorMessage(err))
      setDrafts([])
    } finally {
      setLoading(false)
    }
  }, [enabled, eligible, requirement.id])

  useEffect(() => {
    void loadDrafts()
  }, [loadDrafts])

  if (!enabled || !eligible) return null

  const pending = drafts.filter((d) => d.status === 'pending')
  const confirmed = drafts.filter((d) => d.status === 'confirmed')

  return (
    <section
      className="rounded-lg border border-border bg-card"
      data-testid="fra-ocr-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <h2 className="font-medium">
            {t('compliance.schedule.fra_ocr.panel.title', 'FRA / PAS 79 ingest')}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t(
              'compliance.schedule.fra_ocr.panel.subtitle',
              'Upload a Fire Risk Assessment PDF, review the proposal, then confirm the next due date.',
            )}
          </p>
        </div>
        <FraOcrUploadControl
          requirementId={requirement.id}
          onCreated={(draft) => {
            setDrafts((prev) => [draft, ...prev.filter((d) => d.id !== draft.id)])
            setReviewDraft(draft)
            setReviewOpen(true)
          }}
        />
      </div>

      <div className="space-y-4 p-4 text-sm">
        {loading && drafts.length === 0 ? (
          <p className="text-muted-foreground" data-testid="fra-ocr-loading">
            {t('common.loading', 'Loading…')}
          </p>
        ) : drafts.length === 0 ? (
          <p className="text-muted-foreground" data-testid="fra-ocr-empty">
            {t(
              'compliance.schedule.fra_ocr.panel.empty',
              'No FRA drafts yet. Upload a PAS 79-style PDF to start.',
            )}
          </p>
        ) : (
          <>
            {pending.length > 0 && (
              <div data-testid="fra-ocr-pending-list">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {t('compliance.schedule.fra_ocr.panel.pending', 'Pending review')}
                </h3>
                <ul className="mt-2 divide-y divide-border rounded-lg border border-border">
                  {pending.map((draft) => (
                    <li
                      key={draft.id}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                      data-testid={`fra-ocr-draft-${draft.id}`}
                    >
                      <div className="min-w-0">
                        <div className="font-medium truncate">
                          {draft.source_filename || `Draft #${draft.id}`}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(draft.created_at).toLocaleString()}
                          {draft.warnings?.length
                            ? ` · ${draft.warnings.length} warning${draft.warnings.length === 1 ? '' : 's'}`
                            : ''}
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        data-testid={`fra-ocr-review-${draft.id}`}
                        onClick={() => {
                          setReviewDraft(draft)
                          setReviewOpen(true)
                        }}
                      >
                        {t('compliance.schedule.fra_ocr.panel.review_cta', 'Review')}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {confirmed.length > 0 && (
              <div data-testid="fra-ocr-confirmed-list">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {t('compliance.schedule.fra_ocr.panel.confirmed', 'Confirmed')}
                </h3>
                <ul className="mt-2 divide-y divide-border rounded-lg border border-border">
                  {confirmed.map((draft) => (
                    <li
                      key={draft.id}
                      className="px-3 py-2"
                      data-testid={`fra-ocr-draft-${draft.id}`}
                    >
                      <div className="font-medium truncate">
                        {draft.source_filename || `Draft #${draft.id}`}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {draft.confirmed_at
                          ? new Date(draft.confirmed_at).toLocaleString()
                          : t('compliance.schedule.fra_ocr.panel.confirmed_status', 'Confirmed')}
                      </div>
                      <FraOcrFilingControl
                        draft={draft}
                        onFiled={(updated) => {
                          setDrafts((prev) =>
                            prev.map((d) => (d.id === updated.id ? updated : d)),
                          )
                        }}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>

      <FraOcrReviewSheet
        open={reviewOpen}
        onOpenChange={setReviewOpen}
        draft={reviewDraft}
        onConfirmed={(updatedRequirement) => {
          onRequirementUpdated(updatedRequirement)
          void loadDrafts()
        }}
        onDiscarded={() => {
          void loadDrafts()
        }}
      />
    </section>
  )
}
