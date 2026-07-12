import { AlertTriangle, Loader2, ShieldCheck } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card, CardContent } from '../ui/Card'

type ImportReviewPromoteBannerProps = {
  promoteableCount: number
  acceptedActionCandidates: number
  acceptedRiskCandidates: number
  acceptedClauseCount: number
  jobStatus?: string | null
  showPromoteConfirm: boolean
  isPromoting: boolean
  onPromoteClick: () => void
  onCancelConfirm: () => void
  onConfirmPromote: () => void
}

export function ImportReviewPromoteBanner({
  promoteableCount,
  acceptedActionCandidates,
  acceptedRiskCandidates,
  acceptedClauseCount,
  jobStatus,
  showPromoteConfirm,
  isPromoting,
  onPromoteClick,
  onCancelConfirm,
  onConfirmPromote,
}: ImportReviewPromoteBannerProps) {
  if (showPromoteConfirm) {
    return (
      <Card
        className="border-primary/30 bg-primary/5"
        data-testid="import-review-promote-attest"
        role="status"
      >
        <CardContent className="flex items-center justify-between gap-3 p-5">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <div>
              <p className="text-sm font-medium text-foreground">
                Attest promotion of {promoteableCount} accepted finding(s)?
              </p>
              <p className="text-xs text-muted-foreground">
                Final confirm (click 2 of 2) — creates {promoteableCount} finding(s),{' '}
                {acceptedActionCandidates} corrective action(s), {acceptedRiskCandidates} risk
                escalation(s), and {acceptedClauseCount} evidence link(s) in the live governance
                system. This action cannot be undone.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onCancelConfirm}
              disabled={isPromoting}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={onConfirmPromote} disabled={isPromoting}>
              {isPromoting ? (
                <Loader2 size={14} className="animate-spin" aria-hidden />
              ) : (
                <ShieldCheck size={14} aria-hidden />
              )}
              {isPromoting ? 'Promoting…' : 'Confirm Promote'}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (promoteableCount > 0 && jobStatus === 'review_required') {
    return (
      <div
        className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-900/20 p-4 flex items-center justify-between gap-3"
        data-testid="import-review-promote-ready"
        role="status"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle size={16} className="text-amber-600 shrink-0" />
          <div>
            <p className="text-sm text-amber-800 dark:text-amber-200">
              <strong>{promoteableCount}</strong> accepted finding(s) ready for promotion into the
              live governance system (actions, risk register, audit records).
            </p>
            <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
              Next: Promote Now, then Confirm — two clicks to attest.
            </p>
          </div>
        </div>
        <Button size="sm" onClick={onPromoteClick} disabled={isPromoting}>
          {isPromoting ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
          Promote Now
        </Button>
      </div>
    )
  }

  return null
}
