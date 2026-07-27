/**
 * Close summary dialog for investigations.
 *
 * Mirrors `CaseCloseSummaryDialog` so closing reads the same everywhere, but
 * runs off the investigation's own closure validation: an investigation has
 * report sections and a completion gate rather than a lessons field, so the
 * two cannot share one payload. The API gate is authoritative either way —
 * this dialog only makes the decision an informed one.
 */
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
import type { ClosureValidation, Investigation } from '../../api/investigationsClient'
import { formatCodedValue } from '../../helpers/displayLabels'

export interface InvestigationCloseSummaryDialogProps {
  open: boolean
  investigation: Investigation
  validation: ClosureValidation | null
  submitting?: boolean
  error?: string | null
  onConfirm: () => void
  onOpenChange: (open: boolean) => void
  onOpenActions?: () => void
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

export function InvestigationCloseSummaryDialog({
  open,
  investigation,
  validation,
  submitting = false,
  error,
  onConfirm,
  onOpenChange,
  onOpenActions,
}: InvestigationCloseSummaryDialogProps) {
  const { t } = useTranslation()
  const openWork = validation?.open_work ?? []
  const missingItems = validation?.missing_items ?? []
  const canConfirm = Boolean(validation?.can_close) && !submitting

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" data-testid="investigation-close-summary-dialog">
        <DialogHeader>
          <DialogTitle>
            {t('investigations.closure.close_cta', 'Close investigation')}
          </DialogTitle>
          <DialogDescription>
            {t(
              'caseClosure.description',
              'Check the record over before it becomes a closed, evidential entry.',
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <section className="rounded-lg border border-border p-3">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className="font-mono text-sm text-primary">{investigation.reference_number}</span>
              <Badge variant="outline">{formatCodedValue(investigation.status)}</Badge>
              <span aria-hidden="true" className="text-muted-foreground">
                →
              </span>
              <Badge variant="closed">{formatCodedValue('closed')}</Badge>
            </div>
            <p className="text-sm font-medium text-foreground break-words">{investigation.title}</p>
            <div className="mt-2 divide-y divide-border">
              {investigation.level ? (
                <SummaryRow
                  label={t('investigations.meta.level', 'Level')}
                  value={formatCodedValue(investigation.level)}
                />
              ) : null}
              {investigation.assigned_entity_reference ? (
                <SummaryRow
                  label={t('investigations.handoff.proof_source', 'Source record')}
                  value={investigation.assigned_entity_reference}
                />
              ) : null}
            </div>
          </section>

          {openWork.length > 0 ? (
            <div
              className="rounded-lg border border-warning/40 bg-warning/5 p-4"
              data-testid="investigation-close-summary-open-work"
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

          <section>
            <ul className="space-y-1" data-testid="investigation-close-summary-checklist">
              <ChecklistRow
                ok={missingItems.length === 0}
                label={t('caseClosure.checkSections', 'Required report sections complete')}
              />
              <ChecklistRow
                ok={openWork.length === 0}
                label={t('caseClosure.checkActions', 'No incomplete actions')}
              />
            </ul>
          </section>

          {error ? (
            <p className="text-sm text-destructive" role="alert" data-testid="investigation-close-summary-error">
              {error}
            </p>
          ) : null}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button
            onClick={onConfirm}
            disabled={!canConfirm}
            data-testid="investigation-close-summary-confirm"
          >
            {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" aria-hidden="true" /> : null}
            {t('investigations.closure.close_cta', 'Close investigation')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
