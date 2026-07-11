import { LoadingSkeleton } from '../ui/LoadingSkeleton'
import { ImportReviewHeader } from './ImportReviewHeader'

type ImportReviewLoadingStateProps = {
  specialistHomeLabel: string
  onOpenSpecialistHome: () => void
}

export function ImportReviewLoadingState({
  specialistHomeLabel,
  onOpenSpecialistHome,
}: ImportReviewLoadingStateProps) {
  return (
    <div className="space-y-6 p-6 animate-fade-in">
      <ImportReviewHeader
        pendingDraftCount={0}
        promoteableCount={0}
        isBulkReviewing={false}
        isPromoting={false}
        hasJob={false}
        jobStatus={null}
        specialistHomeLabel={specialistHomeLabel}
        onBulkApprove={() => {}}
        onOpenSpecialistHome={onOpenSpecialistHome}
        onPromoteClick={() => {}}
      />
      <LoadingSkeleton variant="card" rows={5} />
    </div>
  )
}
