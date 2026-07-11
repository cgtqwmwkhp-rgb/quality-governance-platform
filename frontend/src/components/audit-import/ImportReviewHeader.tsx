import { CheckCircle2, FileText, Loader2, ShieldCheck } from 'lucide-react'
import { Button } from '../ui/Button'
import { ImportReviewStepper } from './ImportReviewStepper'

type ImportReviewHeaderProps = {
  pendingDraftCount: number
  promoteableCount: number
  isBulkReviewing: boolean
  isPromoting: boolean
  isProcessing?: boolean
  hasJob: boolean
  jobStatus?: string | null
  specialistHomeLabel: string
  onBulkApprove: () => void
  onOpenSpecialistHome: () => void
  onPromoteClick: () => void
}

export function ImportReviewHeader({
  pendingDraftCount,
  promoteableCount,
  isBulkReviewing,
  isPromoting,
  isProcessing = false,
  hasJob,
  jobStatus,
  specialistHomeLabel,
  onBulkApprove,
  onOpenSpecialistHome,
  onPromoteClick,
}: ImportReviewHeaderProps) {
  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h1 className="text-3xl font-bold text-foreground">External Audit Review</h1>
        <h2 className="sr-only">Import review workspace</h2>
        <p className="mt-1 text-muted-foreground">
          OCR and analysis stay in draft until you approve promotion into completed governance
          outcomes.
        </p>
        <ImportReviewStepper
          hasJob={hasJob}
          jobStatus={jobStatus}
          isProcessing={isProcessing}
          promoteableCount={promoteableCount}
        />
      </div>
      <div className="flex gap-3">
        <Button
          variant="outline"
          onClick={onBulkApprove}
          disabled={!hasJob || pendingDraftCount === 0 || isBulkReviewing || isPromoting}
        >
          {isBulkReviewing ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <CheckCircle2 size={16} />
          )}
          Approve All Pending
        </Button>
        <Button variant="outline" onClick={onOpenSpecialistHome} disabled={!hasJob}>
          <FileText size={16} />
          {specialistHomeLabel}
        </Button>
        <Button
          onClick={onPromoteClick}
          disabled={
            promoteableCount === 0 ||
            isPromoting ||
            jobStatus === 'completed' ||
            jobStatus === 'promoting'
          }
        >
          {isPromoting ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
          Promote Accepted Drafts
        </Button>
      </div>
    </div>
  )
}
