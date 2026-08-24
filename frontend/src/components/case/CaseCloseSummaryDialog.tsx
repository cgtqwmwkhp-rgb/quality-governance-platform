/**
 * Close summary dialog shared by incidents, complaints, near misses and RTAs.
 *
 * Closing a case is not a blind status flip: the operator sees what they are
 * signing off, what is still outstanding, and can capture lessons learnt in
 * place. The API enforces the same gates, so a stale dialog cannot let a case
 * through — this is the informed path to a decision, not the guard.
 */
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, Check, Loader2, X } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/Dialog'
import { Textarea } from '../ui/Textarea'
import { caseClosureApi, getApiErrorMessage } from '../../api/client'
import {
  CLOSURE_REASON_MISSING_LESSONS,
  CLOSURE_REASON_OPEN_ACTIONS,
  type CaseClosureCaseType,
  type CaseClosureValidation,
} from '../../api/caseClosureClient'
import { formatCodedValue } from '../../helpers/displayLabels'
import { formatDisplayDate } from '../../helpers/formatters'

export interface CaseCloseSummaryDialogProps {
  open: boolean
  caseType: CaseClosureCaseType
  caseId: number
  /** Resolves when the close succeeded; rejects to keep the dialog open. */
  onConfirm: (payload: { lessons_learnt?: string }) => Promise<void>
  onOpenChange: (open: boolean) => void
  /** Where "Go to actions" should take the operator, when the page has a tab for it. */
  onOpenActions?: () => void
  testIdPrefix?: string
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <span className="text-xs uppercase tracking-wide text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm text-foreground text-right break-words">{value}</span>
    </div>
  )
}

function ChecklistRow({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      {ok ? (
        <Check className="w-4 h-4 text-success shrink-0" aria-hidden="true" />
      ) : (
        <X className="w-4 h-4 text-destructive shrink-0" aria-hidden="true" />
      )}
      <span className={ok ? 'text-foreground' : 'text-destructive'}>{label}</span>
    </li>
  )
}

export function CaseCloseSummaryDialog({
  open,
  caseType,
  caseId,
  onConfirm,
  onOpenChange,
  onOpenActions,
  testIdPrefix = 'case',
}: CaseCloseSummaryDialogProps) {
  const { t } = useTranslation()
  const [validation, setValidation] = useState<CaseClosureValidation | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [lessons, setLessons] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Deliberately free of `t`: a translator identity change must not re-run the
  // effect below, which would refetch and overwrite lessons mid-typing.
  const load = useCallback(
    async ({ seedLessons }: { seedLessons: boolean }) => {
      setLoading(true)
      setLoadFailed(false)
      try {
        const response = await caseClosureApi.getValidation(caseType, caseId)
        setValidation(response.data)
        if (seedLessons) {
          setLessons(response.data.summary.lessons_learnt || '')
        }
      } catch {
        setValidation(null)
        setLoadFailed(true)
      } finally {
        setLoading(false)
      }
    },
    [caseId, caseType],
  )

  useEffect(() => {
    if (!open) return
    setConfirmError(null)
    void load({ seedLessons: true })
  }, [open, load])

  const summary = validation?.summary
  const lessonsPresent = lessons.trim().length > 0
  const openWork = validation?.open_work ?? []
  // The operator can satisfy the lessons gate right here, so only work they
  // cannot fix in this dialog keeps Confirm disabled.
  const blockedByOpenWork = (validation?.reasons ?? []).includes(CLOSURE_REASON_OPEN_ACTIONS)
  // Absent on a server that predates the transition check: treat as allowed so
  // the dialog behaves as it did rather than blocking every close.
  const transitionAllowed = validation?.transition_allowed !== false
  const nextStatuses = validation?.allowed_next_statuses ?? []
  const canConfirm =
    Boolean(validation) && transitionAllowed && !blockedByOpenWork && lessonsPresent && !submitting

  const handleConfirm = async () => {
    if (!canConfirm) return
    setSubmitting(true)
    setConfirmError(null)
    try {
      await onConfirm({ lessons_learnt: lessons.trim() })
      onOpenChange(false)
    } catch (err) {
      setConfirmError(getApiErrorMessage(err, t('caseClosure.closeFailed', 'Could not close this case.')))
      // Re-read readiness: the refusal usually means the record moved under us.
      // The operator's typed lessons stay put — they are the unsaved work here.
      void load({ seedLessons: false })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl"
        data-testid={`${testIdPrefix}-close-summary-dialog`}
        aria-busy={loading}
      >
        <DialogHeader>
          <DialogTitle>{t('caseClosure.title', 'Close case')}</DialogTitle>
          <DialogDescription>
            {t(
              'caseClosure.description',
              'Check the record over before it becomes a closed, evidential entry.',
            )}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div
            className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center"
            role="status"
          >
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
            {t('caseClosure.loading', 'Checking closure readiness…')}
          </div>
        ) : loadFailed ? (
          <div
            className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
            role="alert"
            data-testid={`${testIdPrefix}-close-summary-load-error`}
          >
            <p>{t('caseClosure.loadFailed', 'Could not check closure readiness.')}</p>
            <Button
              size="sm"
              variant="outline"
              className="mt-3"
              onClick={() => void load({ seedLessons: true })}
            >
              {t('caseClosure.retry', 'Try again')}
            </Button>
          </div>
        ) : summary ? (
          <div className="space-y-4">
            <section
              aria-label={t('caseClosure.identity', 'Case')}
              className="rounded-lg border border-border p-3"
            >
              <div className="flex items-center gap-2 flex-wrap mb-2">
                <span className="font-mono text-sm text-primary">
                  {summary.reference_number || `#${summary.id}`}
                </span>
                <Badge variant="outline">{formatCodedValue(summary.status)}</Badge>
                <span aria-hidden="true" className="text-muted-foreground">
                  →
                </span>
                <Badge variant="closed">{formatCodedValue(summary.target_status)}</Badge>
              </div>
              <p className="text-sm font-medium text-foreground break-words">
                {summary.title || t('caseClosure.untitled', 'Untitled case')}
              </p>
              <div className="mt-2 divide-y divide-border">
                {summary.category ? (
                  <SummaryRow
                    label={t('caseClosure.category', 'Type')}
                    value={formatCodedValue(summary.category)}
                  />
                ) : null}
                {summary.severity ? (
                  <SummaryRow
                    label={t('caseClosure.severity', 'Severity')}
                    value={formatCodedValue(summary.severity)}
                  />
                ) : null}
                {summary.occurred_at ? (
                  <SummaryRow
                    label={t('caseClosure.occurred', 'Occurred')}
                    value={formatDisplayDate(summary.occurred_at)}
                  />
                ) : null}
                {summary.reported_at ? (
                  <SummaryRow
                    label={t('caseClosure.reported', 'Reported')}
                    value={formatDisplayDate(summary.reported_at)}
                  />
                ) : null}
                {summary.linked_investigation ? (
                  <SummaryRow
                    label={t('caseClosure.investigation', 'Investigation')}
                    value={`${
                      summary.linked_investigation.reference_number ||
                      summary.linked_investigation.title ||
                      `#${summary.linked_investigation.id}`
                    } · ${formatCodedValue(summary.linked_investigation.status || '')}`}
                  />
                ) : null}
              </div>
            </section>

            {!transitionAllowed ? (
              <div
                className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm"
                role="alert"
                data-testid={`${testIdPrefix}-close-summary-transition-blocked`}
              >
                <p className="font-medium text-destructive">
                  {t('caseClosure.transitionBlockedTitle', {
                    defaultValue: 'This case cannot close from {{from}}',
                    from: formatCodedValue(summary.status),
                  })}
                </p>
                <p className="mt-1 text-muted-foreground">
                  {nextStatuses.length > 0
                    ? t('caseClosure.transitionBlockedNext', {
                        defaultValue: 'Move it to {{statuses}} first.',
                        statuses: nextStatuses.map((s) => formatCodedValue(s)).join(' or '),
                      })
                    : t(
                        'caseClosure.transitionBlockedDeadEnd',
                        'No route from this status to closed. Ask an administrator.',
                      )}
                </p>
              </div>
            ) : null}

            <section aria-label={t('caseClosure.actions', 'Actions')}>
              <p className="text-sm text-foreground">
                {t('caseClosure.actionsCount', {
                  defaultValue: '{{complete}} of {{total}} actions complete',
                  complete: summary.actions_complete,
                  total: summary.actions_total,
                })}
              </p>
              {openWork.length > 0 ? (
                <div
                  className="mt-2 rounded-lg border border-warning/40 bg-warning/5 p-3"
                  data-testid={`${testIdPrefix}-close-summary-open-work`}
                >
                  <p className="flex items-center gap-2 text-sm font-medium text-warning">
                    <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
                    {t('caseClosure.openWorkTitle', 'Outstanding work blocks closure')}
                  </p>
                  <ul className="mt-2 space-y-1">
                    {openWork.map((item) => (
                      <li key={item.action_key} className="text-sm text-foreground">
                        <span className="font-mono text-xs text-muted-foreground mr-2">
                          {item.reference_number}
                        </span>
                        {item.title || item.kind}
                        <span className="text-muted-foreground"> · {formatCodedValue(item.status)}</span>
                      </li>
                    ))}
                  </ul>
                  {onOpenActions ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-3"
                      onClick={() => {
                        onOpenChange(false)
                        onOpenActions()
                      }}
                    >
                      {t('caseClosure.goToActions', 'Go to actions')}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </section>

            <section aria-label={t('caseClosure.lessons', 'Lessons learnt')}>
              <label
                className="text-sm font-medium text-foreground"
                htmlFor={`${testIdPrefix}-close-lessons`}
              >
                {t('caseClosure.lessons', 'Lessons learnt')}
              </label>
              <Textarea
                id={`${testIdPrefix}-close-lessons`}
                className="mt-1"
                rows={4}
                value={lessons}
                onChange={(e) => setLessons(e.target.value)}
                placeholder={t(
                  'caseClosure.lessonsPlaceholder',
                  'What did this case teach us, and what changes because of it?',
                )}
                data-testid={`${testIdPrefix}-close-lessons`}
              />
            </section>

            <section aria-label={t('caseClosure.checklist', 'Readiness')}>
              <ul className="space-y-1" data-testid={`${testIdPrefix}-close-summary-checklist`}>
                <ChecklistRow
                  ok={lessonsPresent}
                  label={t('caseClosure.checkLessons', 'Lessons learnt recorded')}
                />
                <ChecklistRow
                  ok={!blockedByOpenWork}
                  label={t('caseClosure.checkActions', 'No incomplete actions')}
                />
                <ChecklistRow
                  ok={transitionAllowed}
                  label={t('caseClosure.checkTransition', 'Status can move to closed')}
                />
              </ul>
            </section>

            {confirmError ? (
              <p
                className="text-sm text-destructive"
                role="alert"
                data-testid={`${testIdPrefix}-close-summary-error`}
              >
                {confirmError}
              </p>
            ) : null}
          </div>
        ) : null}

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            {t('cancel', 'Cancel')}
          </Button>
          <Button
            onClick={() => void handleConfirm()}
            disabled={!canConfirm}
            data-testid={`${testIdPrefix}-close-summary-confirm`}
          >
            {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" aria-hidden="true" /> : null}
            {t('caseClosure.confirm', 'Close case')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export { CLOSURE_REASON_MISSING_LESSONS, CLOSURE_REASON_OPEN_ACTIONS }
