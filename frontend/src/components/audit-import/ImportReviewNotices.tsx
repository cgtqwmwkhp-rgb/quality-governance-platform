import { AlertCircle, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import type { ExternalAuditImportJob } from '../../api/client'
import { Button } from '../ui/Button'
import { Card, CardContent } from '../ui/Card'
import type { PromotionFailedDraftRow } from './importReviewHelpers'

type ImportReviewNoticesProps = {
  section: 'pre-proof' | 'post-proof'
  successMessage: string | null
  onDismissSuccess: () => void
  reconciliationNotice: string | null
  error: string | null
  promotionFailedDrafts: PromotionFailedDraftRow[] | null
  onRetryLoad: () => void
  queueNotice: string | null
  job: ExternalAuditImportJob | null
  isQueueing: boolean
  onRetryQueue: () => void
}

export function ImportReviewNotices({
  section,
  successMessage,
  onDismissSuccess,
  reconciliationNotice,
  error,
  promotionFailedDrafts,
  onRetryLoad,
  queueNotice,
  job,
  isQueueing,
  onRetryQueue,
}: ImportReviewNoticesProps) {
  if (section === 'pre-proof') {
    return (
      <>
        {successMessage ? (
          <Card className="border-emerald-300 bg-emerald-50" role="alert">
            <CardContent className="flex items-center justify-between gap-3 p-5">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                <p className="text-sm text-emerald-800">{successMessage}</p>
              </div>
              <Button variant="outline" size="sm" onClick={onDismissSuccess}>
                Dismiss
              </Button>
            </CardContent>
          </Card>
        ) : null}

        {reconciliationNotice ? (
          <Card className="border-amber-300 bg-amber-50" role="status">
            <CardContent className="flex items-center gap-3 p-5">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              <p className="text-sm text-amber-900">{reconciliationNotice}</p>
            </CardContent>
          </Card>
        ) : null}
      </>
    )
  }

  return (
    <>
      {error ? (
        <Card className="border-destructive/30 bg-destructive/5" role="alert">
          <CardContent className="space-y-3 p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <p className="text-sm text-destructive">{error}</p>
              </div>
              <Button variant="outline" size="sm" onClick={onRetryLoad}>
                Retry
              </Button>
            </div>
            {promotionFailedDrafts && promotionFailedDrafts.length > 0 ? (
              <details className="rounded-md border border-destructive/20 bg-background/80 p-3 text-sm">
                <summary className="cursor-pointer font-medium text-foreground">
                  First {promotionFailedDrafts.length} draft failure(s) from server
                </summary>
                <ul className="mt-2 list-inside list-disc space-y-1 text-muted-foreground">
                  {promotionFailedDrafts.map((row, idx) => (
                    <li key={`promo-fail-${row.draft_id ?? idx}`}>
                      {row.draft_id != null ? <>Draft #{row.draft_id}: </> : null}
                      {row.error_type ? (
                        <span className="text-foreground">[{row.error_type}] </span>
                      ) : null}
                      {row.title ? <span className="text-foreground">{row.title} — </span> : null}
                      {row.error ?? 'Unknown error'}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {queueNotice ? (
        <Card className="border-warning/30 bg-warning/5">
          <CardContent className="flex items-center justify-between gap-3 p-5">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-warning" />
              <p className="text-sm text-foreground">{queueNotice}</p>
            </div>
            {job?.status === 'pending' || job?.status === 'failed' ? (
              <Button variant="outline" size="sm" onClick={onRetryQueue} disabled={isQueueing}>
                {isQueueing ? <Loader2 size={16} className="animate-spin" /> : null}
                Retry Queue
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </>
  )
}
