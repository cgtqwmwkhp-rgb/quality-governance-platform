import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, CheckCircle2, Link2, Loader2, UserPlus } from 'lucide-react'
import { Badge, type BadgeVariant } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/Dialog'
import { Textarea } from '../ui/Textarea'
import { cn } from '../../helpers/utils'

export type LoopCapaSnapshot = {
  id: number
  action_key: string
  display_status: string
  status: string
  assigned_to_email?: string | null
  reference_number?: string | null
} | null

export type CapaLoopLoadState = 'loading' | 'ready' | 'unavailable' | 'missing'

const CAPA_CLOSED_STATUSES = new Set([
  'completed',
  'closed',
  'cancelled',
  'verified',
])

/** True when closing the finding should require an honest supervisor override. */
export function isCapaBlockingClose(
  capa: LoopCapaSnapshot,
  loadState: CapaLoopLoadState,
  correctiveActionRequired: boolean,
): boolean {
  if (!correctiveActionRequired && loadState === 'missing') {
    return false
  }
  if (loadState === 'loading') {
    return true
  }
  if (loadState === 'unavailable') {
    // Sibling CAPA bridge / actions API may be down — never pretend the loop is clear.
    return true
  }
  if (loadState === 'missing') {
    return correctiveActionRequired
  }
  if (!capa) {
    return correctiveActionRequired
  }
  return !CAPA_CLOSED_STATUSES.has(String(capa.display_status || capa.status || '').toLowerCase())
}

function statusVariant(status: string): BadgeVariant {
  const normalized = status.toLowerCase()
  if (CAPA_CLOSED_STATUSES.has(normalized)) return 'success'
  if (normalized === 'pending_verification' || normalized === 'verification') return 'warning'
  if (normalized === 'in_progress' || normalized === 'overdue') return 'warning'
  if (normalized === 'open') return 'destructive'
  return 'secondary'
}

export type FindingLoopStatusRibbonProps = {
  findingId: number
  findingStatus: string
  correctiveActionRequired: boolean
  capa: LoopCapaSnapshot
  capaLoadState: CapaLoopLoadState
  riskLinked: boolean
  riskCount: number
  assigning?: boolean
  closing?: boolean
  onAssignCapa: (email: string) => Promise<void>
  onOpenCapa: () => void
  onOpenRisk: () => void
  onCloseFinding: (opts: {
    override: boolean
    reason?: string
    note?: string
  }) => Promise<void>
}

export function FindingLoopStatusRibbon({
  findingId,
  findingStatus,
  correctiveActionRequired,
  capa,
  capaLoadState,
  riskLinked,
  riskCount,
  assigning = false,
  closing = false,
  onAssignCapa,
  onOpenCapa,
  onOpenRisk,
  onCloseFinding,
}: FindingLoopStatusRibbonProps) {
  const { t } = useTranslation()
  const [assignEmail, setAssignEmail] = useState(capa?.assigned_to_email || '')
  const [showAssign, setShowAssign] = useState(false)
  const [showClose, setShowClose] = useState(false)
  const [override, setOverride] = useState(false)
  const [overrideReason, setOverrideReason] = useState('')
  const [closeNote, setCloseNote] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const blocked = isCapaBlockingClose(capa, capaLoadState, correctiveActionRequired)
  const findingClosed = findingStatus.toLowerCase() === 'closed'
  const capaLabel =
    capaLoadState === 'loading'
      ? t('audits.findings.loop.capa_loading')
      : capaLoadState === 'unavailable'
        ? t('audits.findings.loop.capa_unavailable')
        : capaLoadState === 'missing' || !capa
          ? t('audits.findings.loop.capa_missing')
          : capa.display_status || capa.status

  const riskLabel = riskLinked
    ? t('audits.findings.loop.risk_linked', { count: riskCount })
    : t('audits.findings.loop.risk_pending')

  const loopComplete =
    findingClosed && !blocked && (riskLinked || !correctiveActionRequired)

  const submitAssign = async () => {
    const email = assignEmail.trim()
    if (!email) {
      setLocalError(t('audits.findings.loop.assign_email_required'))
      return
    }
    setLocalError(null)
    try {
      await onAssignCapa(email)
      setShowAssign(false)
    } catch {
      setLocalError(t('audits.findings.loop.assign_failed'))
    }
  }

  const submitClose = async () => {
    if (findingClosed) return
    if (blocked && !override) {
      setLocalError(t('audits.findings.loop.override_required'))
      return
    }
    if (blocked && override && !overrideReason.trim()) {
      setLocalError(t('audits.findings.loop.override_reason_required'))
      return
    }
    setLocalError(null)
    try {
      await onCloseFinding({
        override: blocked && override,
        reason: overrideReason.trim() || undefined,
        note: closeNote.trim() || undefined,
      })
      setShowClose(false)
      setOverride(false)
      setOverrideReason('')
      setCloseNote('')
    } catch {
      setLocalError(t('audits.findings.loop.close_failed'))
    }
  }

  return (
    <div
      className="mt-4 rounded-lg border border-border/80 bg-muted/20 p-3 space-y-3"
      data-testid={`finding-loop-ribbon-${findingId}`}
      data-loop-complete={loopComplete ? 'true' : 'false'}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t('audits.findings.loop.title')}
        </p>
        {loopComplete ? (
          <Badge variant="success" data-testid={`finding-loop-complete-${findingId}`}>
            <CheckCircle2 className="mr-1 h-3 w-3" aria-hidden />
            {t('audits.findings.loop.complete')}
          </Badge>
        ) : null}
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <div className="rounded-md border border-border bg-background/60 p-2">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {t('audits.findings.loop.finding')}
          </p>
          <Badge
            variant={statusVariant(findingStatus)}
            className="mt-1"
            data-testid={`finding-loop-finding-status-${findingId}`}
          >
            {findingStatus.replace(/_/g, ' ')}
          </Badge>
        </div>
        <div className="rounded-md border border-border bg-background/60 p-2">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {t('audits.findings.loop.capa')}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            {capaLoadState === 'loading' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" aria-hidden />
            ) : null}
            <Badge
              variant={
                capaLoadState === 'unavailable' || capaLoadState === 'missing'
                  ? 'warning'
                  : statusVariant(String(capa?.display_status || capa?.status || 'open'))
              }
              data-testid={`finding-loop-capa-status-${findingId}`}
            >
              {capaLabel}
            </Badge>
            {capa?.assigned_to_email ? (
              <span
                className="text-xs text-muted-foreground truncate max-w-[10rem]"
                data-testid={`finding-loop-capa-assignee-${findingId}`}
                title={capa.assigned_to_email}
              >
                {capa.assigned_to_email}
              </span>
            ) : (
              <span
                className="text-xs text-muted-foreground"
                data-testid={`finding-loop-capa-assignee-${findingId}`}
              >
                {t('audits.findings.loop.unassigned')}
              </span>
            )}
          </div>
        </div>
        <div className="rounded-md border border-border bg-background/60 p-2">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {t('audits.findings.loop.risk')}
          </p>
          <Badge
            variant={riskLinked ? 'success' : 'secondary'}
            className="mt-1"
            data-testid={`finding-loop-risk-status-${findingId}`}
          >
            <Link2 className="mr-1 h-3 w-3" aria-hidden />
            {riskLabel}
          </Badge>
        </div>
      </div>

      {blocked && !findingClosed ? (
        <div
          className="flex items-start gap-2 rounded-md border border-amber-300/60 bg-amber-50/80 px-2.5 py-2 text-xs text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
          data-testid={`finding-loop-gate-${findingId}`}
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <p>{t('audits.findings.loop.gate_hint')}</p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="secondary"
          data-testid={`finding-loop-assign-${findingId}`}
          disabled={findingClosed || assigning}
          onClick={(e) => {
            e.stopPropagation()
            setShowAssign(true)
            setLocalError(null)
            setAssignEmail(capa?.assigned_to_email || '')
          }}
        >
          <UserPlus className="mr-1 h-3.5 w-3.5" aria-hidden />
          {capa ? t('audits.findings.loop.assign_capa') : t('audits.findings.loop.create_assign_capa')}
        </Button>
        {capa ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            data-testid={`finding-loop-open-capa-${findingId}`}
            onClick={(e) => {
              e.stopPropagation()
              onOpenCapa()
            }}
          >
            {t('audits.findings.loop.open_capa')}
          </Button>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="outline"
          data-testid={`finding-loop-open-risk-${findingId}`}
          onClick={(e) => {
            e.stopPropagation()
            onOpenRisk()
          }}
        >
          {riskLinked
            ? t('audits.findings.loop.open_risk')
            : t('audits.findings.loop.view_risk')}
        </Button>
        {!findingClosed ? (
          <Button
            type="button"
            size="sm"
            variant={blocked ? 'outline' : 'default'}
            className={cn(blocked && 'border-amber-500/50')}
            data-testid={`finding-loop-close-${findingId}`}
            disabled={closing || capaLoadState === 'loading'}
            onClick={(e) => {
              e.stopPropagation()
              setShowClose(true)
              setOverride(false)
              setOverrideReason('')
              setCloseNote('')
              setLocalError(null)
            }}
          >
            {t('audits.findings.loop.close_finding')}
          </Button>
        ) : null}
      </div>

      <Dialog open={showAssign} onOpenChange={setShowAssign}>
        <DialogContent
          className="sm:max-w-md"
          onClick={(e) => e.stopPropagation()}
          data-testid={`finding-loop-assign-dialog-${findingId}`}
        >
          <DialogHeader>
            <DialogTitle>{t('audits.findings.loop.assign_dialog_title')}</DialogTitle>
            <DialogDescription>
              {t('audits.findings.loop.assign_dialog_body')}
            </DialogDescription>
          </DialogHeader>
          <Input
            type="email"
            value={assignEmail}
            onChange={(e) => setAssignEmail(e.target.value)}
            placeholder="user@company.com"
            data-testid={`finding-loop-assign-email-${findingId}`}
            aria-label={t('audits.findings.loop.assign_email_label')}
          />
          {localError ? (
            <p className="text-sm text-destructive" role="alert">
              {localError}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setShowAssign(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              type="button"
              disabled={assigning}
              data-testid={`finding-loop-assign-submit-${findingId}`}
              onClick={() => void submitAssign()}
            >
              {assigning ? <Loader2 className="h-4 w-4 animate-spin" /> : t('audits.findings.loop.assign_submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showClose} onOpenChange={setShowClose}>
        <DialogContent
          className="sm:max-w-md"
          onClick={(e) => e.stopPropagation()}
          data-testid={`finding-loop-close-dialog-${findingId}`}
        >
          <DialogHeader>
            <DialogTitle>{t('audits.findings.loop.close_dialog_title')}</DialogTitle>
            <DialogDescription>
              {blocked
                ? t('audits.findings.loop.close_dialog_blocked')
                : t('audits.findings.loop.close_dialog_body')}
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={closeNote}
            onChange={(e) => setCloseNote(e.target.value)}
            placeholder={t('audits.findings.loop.verification_note_placeholder')}
            data-testid={`finding-loop-close-note-${findingId}`}
            rows={2}
          />
          {blocked ? (
            <div className="space-y-2 rounded-md border border-amber-300/70 bg-amber-50/70 p-3 dark:border-amber-700 dark:bg-amber-950/40">
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={override}
                  onChange={(e) => setOverride(e.target.checked)}
                  data-testid={`finding-loop-override-${findingId}`}
                />
                <span>{t('audits.findings.loop.override_label')}</span>
              </label>
              {override ? (
                <Textarea
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder={t('audits.findings.loop.override_reason_placeholder')}
                  data-testid={`finding-loop-override-reason-${findingId}`}
                  rows={2}
                />
              ) : null}
            </div>
          ) : null}
          {localError ? (
            <p className="text-sm text-destructive" role="alert">
              {localError}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setShowClose(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              type="button"
              disabled={closing || (blocked && !override)}
              data-testid={`finding-loop-close-submit-${findingId}`}
              onClick={() => void submitClose()}
            >
              {closing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : blocked ? (
                t('audits.findings.loop.close_with_override')
              ) : (
                t('audits.findings.loop.close_submit')
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
