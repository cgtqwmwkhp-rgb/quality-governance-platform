import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/Label'
import { Textarea } from '../../components/ui/Textarea'
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../../components/ui/Sheet'
import { complianceScheduleFraOcrApi, getApiErrorMessage } from '../../api/client'
import type {
  FraActionPriority,
  FraExtractedField,
  FraOcrDraftResponse,
  FraProposedAction,
} from '../../api/complianceScheduleFraOcrClient'
import type { ComplianceRequirement } from '../../api/complianceScheduleClient'
import { toast } from '../../contexts/ToastContext'
import { useFeatureFlag } from '../../hooks/useFeatureFlag'
import { confidenceChipClass, proposeNextDueDate } from './fraOcrHelpers'

const SELECT_CLASS =
  'w-full appearance-none rounded-lg border border-border bg-background px-3 py-2 text-sm ' +
  'text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50'

const FIELD_KEYS: Array<{ key: keyof FraOcrDraftResponse['proposed']; label: string }> = [
  { key: 'assessment_date', label: 'Assessment date' },
  { key: 'next_review_date', label: 'Next review date' },
  { key: 'review_interval_months', label: 'Review interval (months)' },
  { key: 'assessor_name', label: 'Assessor name' },
  { key: 'assessor_organisation', label: 'Assessor organisation' },
  { key: 'premises_name', label: 'Premises name' },
  { key: 'pas79_reference', label: 'PAS 79 reference' },
  { key: 'overall_risk_rating', label: 'Overall risk rating' },
]

interface EditableAction {
  index: number
  selected: boolean
  text: string
  priority_normalised: FraActionPriority | ''
  target_date: string
  needs_review: boolean
  source_ref?: string | null
  confidence: FraProposedAction['confidence']
}

function toEditableActions(actions: FraProposedAction[]): EditableAction[] {
  return actions.map((action) => ({
    index: action.index,
    // needs_review rows start unchecked; everything else is included by default.
    selected: !action.needs_review,
    text: action.text,
    priority_normalised: action.priority_normalised ?? '',
    target_date: action.target_date ?? '',
    needs_review: action.needs_review,
    source_ref: action.source_ref,
    confidence: action.confidence,
  }))
}

interface FraOcrReviewSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  draft: FraOcrDraftResponse | null
  onConfirmed: (requirement: ComplianceRequirement) => void
  onDiscarded?: () => void
}

/**
 * The human gate. Nothing on the requirement moves until Confirm sends an
 * explicit ``next_due_date`` the operator has focused and blurred — a prefilled
 * proposal the operator never looked at is not a gate.
 */
export function FraOcrReviewSheet({
  open,
  onOpenChange,
  draft,
  onConfirmed,
  onDiscarded,
}: FraOcrReviewSheetProps) {
  const { t } = useTranslation()
  const [nextDueDate, setNextDueDate] = useState('')
  const [dueDateTouched, setDueDateTouched] = useState(false)
  const [actions, setActions] = useState<EditableAction[]>([])
  const [note, setNote] = useState('')
  const [proposeRisk, setProposeRisk] = useState(false)
  const [riskLikelihood, setRiskLikelihood] = useState('')
  const [riskImpact, setRiskImpact] = useState('')
  const [riskTitle, setRiskTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const riskEnabled = useFeatureFlag('compliance_schedule_fra_ocr_risk')

  useEffect(() => {
    if (!open || !draft) return
    setNextDueDate(proposeNextDueDate(draft))
    setDueDateTouched(false)
    setActions(toEditableActions(draft.proposed_actions ?? []))
    setNote('')
    setProposeRisk(false)
    setRiskLikelihood('')
    setRiskImpact('')
    setRiskTitle('')
    setBusy(false)
  }, [open, draft])

  const canConfirm = useMemo(() => {
    if (!nextDueDate || !dueDateTouched || busy) return false
    if (riskEnabled && proposeRisk) {
      const l = Number(riskLikelihood)
      const i = Number(riskImpact)
      if (!Number.isInteger(l) || !Number.isInteger(i) || l < 1 || l > 5 || i < 1 || i > 5) {
        return false
      }
    }
    return true
  }, [
    nextDueDate,
    dueDateTouched,
    busy,
    riskEnabled,
    proposeRisk,
    riskLikelihood,
    riskImpact,
  ])

  const updateAction = (index: number, patch: Partial<EditableAction>) => {
    setActions((prev) => prev.map((row) => (row.index === index ? { ...row, ...patch } : row)))
  }

  const handleConfirm = async () => {
    if (!draft || !canConfirm) return
    setBusy(true)
    try {
      const selected = actions
        .filter((row) => row.selected && row.text.trim())
        .map((row) => ({
          index: row.index,
          text: row.text.trim(),
          ...(row.priority_normalised
            ? { priority_normalised: row.priority_normalised as FraActionPriority }
            : {}),
          ...(row.target_date ? { target_date: row.target_date } : {}),
        }))
      const riskPayload =
        riskEnabled && proposeRisk
          ? {
              inherent_likelihood: Number(riskLikelihood),
              inherent_impact: Number(riskImpact),
              ...(riskTitle.trim() ? { title: riskTitle.trim() } : {}),
            }
          : undefined
      const response = await complianceScheduleFraOcrApi.confirmDraft(draft.id, {
        next_due_date: nextDueDate,
        acknowledged_warnings: (draft.warnings?.length ?? 0) > 0,
        actions: selected,
        ...(note.trim() ? { note: note.trim() } : {}),
        ...(riskPayload ? { risk: riskPayload } : {}),
      })
      toast.success(
        t('compliance.schedule.fra_ocr.confirm.success', 'FRA proposal applied to the obligation'),
      )
      onOpenChange(false)
      onConfirmed(response.data.requirement)
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const handleDiscard = async () => {
    if (!draft) return
    setBusy(true)
    try {
      await complianceScheduleFraOcrApi.discardDraft(draft.id, {})
      toast.success(t('compliance.schedule.fra_ocr.discard.success', 'FRA draft discarded'))
      onOpenChange(false)
      onDiscarded?.()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="max-w-xl" data-testid="fra-ocr-review-sheet">
        <SheetHeader>
          <SheetTitle>
            {t('compliance.schedule.fra_ocr.review.title', 'Review FRA proposal')}
          </SheetTitle>
          <SheetDescription>
            {draft?.source_filename
              ? draft.source_filename
              : t('compliance.schedule.fra_ocr.review.subtitle', 'Confirm the next due date before applying')}
          </SheetDescription>
        </SheetHeader>
        <SheetBody className="space-y-5">
          {draft && (
            <>
              <section className="space-y-3" data-testid="fra-ocr-proposed-fields">
                <h3 className="text-sm font-medium">
                  {t('compliance.schedule.fra_ocr.review.fields', 'Proposed fields')}
                </h3>
                <dl className="space-y-3 text-sm">
                  {FIELD_KEYS.map(({ key, label }) => {
                    const field = draft.proposed[key]
                    if (!field || typeof field !== 'object' || !('confidence' in field)) return null
                    return (
                      <ProposedFieldRow
                        key={key}
                        label={t(`compliance.schedule.fra_ocr.field.${key}`, label)}
                        field={field as FraExtractedField}
                      />
                    )
                  })}
                  {draft.proposed.risk_vocabulary && (
                    <div>
                      <dt className="text-muted-foreground">
                        {t('compliance.schedule.fra_ocr.field.risk_vocabulary', 'Risk vocabulary')}
                      </dt>
                      <dd className="mt-0.5 font-medium">{draft.proposed.risk_vocabulary}</dd>
                    </div>
                  )}
                </dl>
              </section>

              <div className="space-y-2">
                <Label htmlFor="fra-ocr-next-due" required>
                  {t('compliance.schedule.fra_ocr.review.next_due', 'Next due date')}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {t(
                    'compliance.schedule.fra_ocr.review.next_due_hint',
                    'Look at the proposed date, then confirm or correct it. Confirm stays disabled until you leave this field.',
                  )}
                </p>
                <Input
                  id="fra-ocr-next-due"
                  type="date"
                  value={nextDueDate}
                  data-testid="fra-ocr-next-due-date"
                  disabled={busy}
                  onChange={(e) => setNextDueDate(e.target.value)}
                  onBlur={() => setDueDateTouched(true)}
                />
              </div>

              {(draft.proposed_actions?.length ?? 0) > 0 && (
                <section className="space-y-3" data-testid="fra-ocr-actions">
                  <h3 className="text-sm font-medium">
                    {t('compliance.schedule.fra_ocr.review.actions', 'Priority actions')}
                  </h3>
                  <ul className="space-y-3">
                    {actions.map((row) => (
                      <li
                        key={row.index}
                        className="space-y-2 rounded-lg border border-border p-3"
                        data-testid={`fra-ocr-action-${row.index}`}
                      >
                        <div className="flex items-start gap-2">
                          <input
                            id={`fra-ocr-action-check-${row.index}`}
                            type="checkbox"
                            className="mt-1 h-4 w-4"
                            checked={row.selected}
                            disabled={busy}
                            data-testid={`fra-ocr-action-check-${row.index}`}
                            onChange={(e) => updateAction(row.index, { selected: e.target.checked })}
                          />
                          <div className="min-w-0 flex-1 space-y-2">
                            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              {row.source_ref && <span>{row.source_ref}</span>}
                              {row.needs_review && (
                                <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-800">
                                  {t('compliance.schedule.fra_ocr.needs_review', 'Needs review')}
                                </span>
                              )}
                              <span
                                className={`rounded px-1.5 py-0.5 font-medium ${confidenceChipClass(row.confidence)}`}
                              >
                                {row.confidence}
                              </span>
                            </div>
                            <Textarea
                              value={row.text}
                              disabled={busy || !row.selected}
                              rows={2}
                              data-testid={`fra-ocr-action-text-${row.index}`}
                              onChange={(e) => updateAction(row.index, { text: e.target.value })}
                            />
                            <div className="grid grid-cols-2 gap-2">
                              <label className="block space-y-1">
                                <span className="text-xs text-muted-foreground">
                                  {t('compliance.schedule.fra_ocr.priority', 'Priority')}
                                </span>
                                <select
                                  className={SELECT_CLASS}
                                  value={row.priority_normalised}
                                  disabled={busy || !row.selected}
                                  data-testid={`fra-ocr-action-priority-${row.index}`}
                                  onChange={(e) =>
                                    updateAction(row.index, {
                                      priority_normalised: e.target.value as FraActionPriority | '',
                                    })
                                  }
                                >
                                  <option value="">—</option>
                                  <option value="high">high</option>
                                  <option value="medium">medium</option>
                                  <option value="low">low</option>
                                </select>
                              </label>
                              <label className="block space-y-1">
                                <span className="text-xs text-muted-foreground">
                                  {t('compliance.schedule.fra_ocr.target_date', 'Target date')}
                                </span>
                                <Input
                                  type="date"
                                  value={row.target_date}
                                  disabled={busy || !row.selected}
                                  data-testid={`fra-ocr-action-target-${row.index}`}
                                  onChange={(e) =>
                                    updateAction(row.index, { target_date: e.target.value })
                                  }
                                />
                              </label>
                            </div>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {(draft.warnings?.length ?? 0) > 0 && (
                <section
                  className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
                  data-testid="fra-ocr-warnings"
                >
                  <h3 className="font-medium">
                    {t('compliance.schedule.fra_ocr.review.warnings', 'Warnings')}
                  </h3>
                  <ul className="list-disc space-y-1 pl-4">
                    {draft.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </section>
              )}


              {riskEnabled && (
                <section className="space-y-3" data-testid="fra-ocr-risk-proposal">
                  <h3 className="text-sm font-medium">
                    {t('compliance.schedule.fra_ocr.review.risk', 'Propose risk (optional)')}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {t(
                      'compliance.schedule.fra_ocr.review.risk_hint',
                      'Enter likelihood and impact yourself — OCR ratings are never used as scores.',
                    )}
                  </p>
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4"
                      checked={proposeRisk}
                      disabled={busy}
                      data-testid="fra-ocr-risk-enable"
                      onChange={(e) => setProposeRisk(e.target.checked)}
                    />
                    <span>
                      {t(
                        'compliance.schedule.fra_ocr.review.risk_enable',
                        'Create a risk register entry on confirm',
                      )}
                    </span>
                  </label>
                  {proposeRisk && (
                    <div className="space-y-2">
                      <div className="grid grid-cols-2 gap-2">
                        <label className="block space-y-1">
                          <span className="text-xs text-muted-foreground">
                            {t(
                              'compliance.schedule.fra_ocr.review.risk_likelihood',
                              'Likelihood (1–5)',
                            )}
                          </span>
                          <select
                            className={SELECT_CLASS}
                            value={riskLikelihood}
                            disabled={busy}
                            data-testid="fra-ocr-risk-likelihood"
                            onChange={(e) => setRiskLikelihood(e.target.value)}
                          >
                            <option value="">—</option>
                            {[1, 2, 3, 4, 5].map((n) => (
                              <option key={n} value={String(n)}>
                                {n}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="block space-y-1">
                          <span className="text-xs text-muted-foreground">
                            {t(
                              'compliance.schedule.fra_ocr.review.risk_impact',
                              'Impact (1–5)',
                            )}
                          </span>
                          <select
                            className={SELECT_CLASS}
                            value={riskImpact}
                            disabled={busy}
                            data-testid="fra-ocr-risk-impact"
                            onChange={(e) => setRiskImpact(e.target.value)}
                          >
                            <option value="">—</option>
                            {[1, 2, 3, 4, 5].map((n) => (
                              <option key={n} value={String(n)}>
                                {n}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="fra-ocr-risk-title">
                          {t(
                            'compliance.schedule.fra_ocr.review.risk_title',
                            'Risk title (optional)',
                          )}
                        </Label>
                        <Input
                          id="fra-ocr-risk-title"
                          value={riskTitle}
                          disabled={busy}
                          data-testid="fra-ocr-risk-title"
                          onChange={(e) => setRiskTitle(e.target.value)}
                        />
                      </div>
                    </div>
                  )}
                </section>
              )}

              <div className="space-y-2">
                <Label htmlFor="fra-ocr-note">
                  {t('compliance.schedule.fra_ocr.review.note', 'Note (optional)')}
                </Label>
                <Textarea
                  id="fra-ocr-note"
                  value={note}
                  rows={2}
                  disabled={busy}
                  data-testid="fra-ocr-note"
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>

              <div className="flex flex-wrap justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={busy}
                  data-testid="fra-ocr-discard"
                  onClick={() => void handleDiscard()}
                >
                  {t('compliance.schedule.fra_ocr.discard.cta', 'Discard')}
                </Button>
                <Button
                  type="button"
                  disabled={!canConfirm}
                  data-testid="fra-ocr-confirm"
                  onClick={() => void handleConfirm()}
                >
                  {busy
                    ? t('common.saving', 'Saving…')
                    : t('compliance.schedule.fra_ocr.confirm.cta', 'Confirm')}
                </Button>
              </div>
            </>
          )}
        </SheetBody>
      </SheetContent>
    </Sheet>
  )
}

function ProposedFieldRow({ label, field }: { label: string; field: FraExtractedField }) {
  return (
    <div>
      <dt className="flex flex-wrap items-center gap-2 text-muted-foreground">
        <span>{label}</span>
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-medium ${confidenceChipClass(field.confidence)}`}
        >
          {field.confidence}
        </span>
      </dt>
      <dd className="mt-0.5 font-medium">{field.value?.trim() ? field.value : '—'}</dd>
      {field.evidence_snippet && (
        <p className="mt-0.5 text-xs text-muted-foreground">{field.evidence_snippet}</p>
      )}
    </div>
  )
}
