import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { DraftFindingsList } from '../components/audit-import/DraftFindingsList'
import {
  DownstreamWorkflowProof,
  isCompleteReconciliation,
} from '../components/audit-import/DownstreamWorkflowProof'
import { ImportReviewAuditSummary } from '../components/audit-import/ImportReviewAuditSummary'
import { ImportReviewEvidenceCard } from '../components/audit-import/ImportReviewEvidenceCard'
import { ImportReviewHeader } from '../components/audit-import/ImportReviewHeader'
import { ImportReviewNotices } from '../components/audit-import/ImportReviewNotices'
import { ImportReviewOverview } from '../components/audit-import/ImportReviewOverview'
import { ImportReviewProcessingPanels } from '../components/audit-import/ImportReviewProcessingPanels'
import { ImportReviewPromoteBanner } from '../components/audit-import/ImportReviewPromoteBanner'
import { useImportReviewActions } from '../components/audit-import/useImportReviewActions'
import { useImportReviewDerived } from '../components/audit-import/useImportReviewDerived'
import { useImportReviewLoader } from '../components/audit-import/useImportReviewLoader'

export default function AuditImportReview() {
  const { auditId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const jobId = Number(searchParams.get('jobId') || '')
  const routeAuditId = Number(auditId || '')
  const initialQueueNotice =
    searchParams.get('queueError') === '1'
      ? 'The import workspace is ready, but automatic processing did not start. Retry queueing below.'
      : null

  const {
    job,
    setJob,
    auditRun,
    drafts,
    setDrafts,
    reconciliation,
    setReconciliation,
    loading,
    error,
    setError,
    queueNotice,
    setQueueNotice,
    reconciliationNotice,
    setReconciliationNotice,
    promotionFailedDrafts,
    setPromotionFailedDrafts,
    lastUpdatedAt,
    isProcessing,
    setIsProcessing,
    isDocumentHidden,
    load,
  } = useImportReviewLoader(jobId, routeAuditId, initialQueueNotice)

  const {
    approvedCount,
    promoteableCount,
    pendingDraftCount,
    acceptedClauseCount,
    acceptedActionCandidates,
    acceptedRiskCandidates,
    schemeAlignment,
    declaredProgramLabel,
    declaredSourceOrigin,
    declaredScheme,
    resolvedTemplateVersion,
    resolvedTemplateId,
    resolvedTemplateName,
    declaredExternalBody,
    declaredExternalReference,
    specialistHome,
    specialistHomePath,
  } = useImportReviewDerived(job, auditRun, drafts, reconciliation)

  const {
    busyDraftId,
    isBulkReviewing,
    isPromoting,
    isQueueing,
    showPromoteConfirm,
    setShowPromoteConfirm,
    successMessage,
    dismissSuccess,
    handleDraftDecision,
    handlePromoteClick,
    handleBulkApprove,
    handlePromoteConfirm,
    handleRetryQueue,
  } = useImportReviewActions({
    job,
    setJob,
    setDrafts,
    setReconciliation,
    setError,
    setQueueNotice,
    setReconciliationNotice,
    setPromotionFailedDrafts,
    setIsProcessing,
    load,
    promoteableCount,
    pendingDraftCount,
  })

    // Keep the page chrome visible during load so reviewers (and CUJ e2e) always
  // see the Import Review heading instead of a blank skeleton-only state.
  if (loading) {
    return (
      <div className="space-y-6 p-6 animate-fade-in">
        <ImportReviewHeader
          pendingDraftCount={0}
          promoteableCount={0}
          isBulkReviewing={false}
          isPromoting={false}
          hasJob={false}
          jobStatus={null}
          specialistHomeLabel={specialistHome.label}
          onBulkApprove={() => {}}
          onOpenSpecialistHome={() => navigate(specialistHomePath)}
          onPromoteClick={() => {}}
        />
        <LoadingSkeleton variant="card" rows={5} />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6 animate-fade-in">
      <ImportReviewHeader
        pendingDraftCount={pendingDraftCount}
        promoteableCount={promoteableCount}
        isBulkReviewing={isBulkReviewing}
        isPromoting={isPromoting}
        hasJob={Boolean(job)}
        jobStatus={job?.status}
        specialistHomeLabel={specialistHome.label}
        onBulkApprove={() => void handleBulkApprove()}
        onOpenSpecialistHome={() => navigate(specialistHomePath)}
        onPromoteClick={handlePromoteClick}
      />

      <ImportReviewPromoteBanner
        promoteableCount={promoteableCount}
        acceptedActionCandidates={acceptedActionCandidates}
        acceptedRiskCandidates={acceptedRiskCandidates}
        acceptedClauseCount={acceptedClauseCount}
        jobStatus={job?.status}
        showPromoteConfirm={showPromoteConfirm}
        isPromoting={isPromoting}
        onPromoteClick={handlePromoteClick}
        onCancelConfirm={() => setShowPromoteConfirm(false)}
        onConfirmPromote={() => void handlePromoteConfirm()}
      />

      <ImportReviewNotices
        section="pre-proof"
        successMessage={successMessage}
        onDismissSuccess={dismissSuccess}
        reconciliationNotice={reconciliationNotice}
        error={error}
        promotionFailedDrafts={promotionFailedDrafts}
        onRetryLoad={() => void load()}
        queueNotice={queueNotice}
        job={job}
        isQueueing={isQueueing}
        onRetryQueue={() => void handleRetryQueue()}
      />

      {isCompleteReconciliation(reconciliation) ? (
        <DownstreamWorkflowProof
          reconciliation={reconciliation}
          onNavigate={(path) => navigate(path)}
        />
      ) : null}

      <ImportReviewNotices
        section="post-proof"
        successMessage={successMessage}
        onDismissSuccess={dismissSuccess}
        reconciliationNotice={reconciliationNotice}
        error={error}
        promotionFailedDrafts={promotionFailedDrafts}
        onRetryLoad={() => void load()}
        queueNotice={queueNotice}
        job={job}
        isQueueing={isQueueing}
        onRetryQueue={() => void handleRetryQueue()}
      />

      {job ? (
        <ImportReviewOverview
          job={job}
          drafts={drafts}
          declaredProgramLabel={declaredProgramLabel}
          declaredSourceOrigin={declaredSourceOrigin}
          declaredScheme={declaredScheme}
          resolvedTemplateName={resolvedTemplateName}
          resolvedTemplateId={resolvedTemplateId}
          resolvedTemplateVersion={resolvedTemplateVersion}
          declaredExternalBody={declaredExternalBody}
          declaredExternalReference={declaredExternalReference}
          approvedCount={approvedCount}
          promoteableCount={promoteableCount}
          isProcessing={isProcessing}
          lastUpdatedAt={lastUpdatedAt}
          isDocumentHidden={isDocumentHidden}
        />
      ) : null}

      {job ? <ImportReviewAuditSummary job={job} /> : null}

      <ImportReviewProcessingPanels
        job={job}
        isProcessing={isProcessing}
        isQueueing={isQueueing}
        onRetryQueue={() => void handleRetryQueue()}
      />

      {job ? (
        <ImportReviewEvidenceCard
          job={job}
          approvedCount={approvedCount}
          acceptedClauseCount={acceptedClauseCount}
          acceptedActionCandidates={acceptedActionCandidates}
          acceptedRiskCandidates={acceptedRiskCandidates}
          schemeAlignment={schemeAlignment}
        />
      ) : null}

      <DraftFindingsList
        drafts={drafts}
        job={job}
        error={error}
        busyDraftId={busyDraftId}
        isBulkReviewing={isBulkReviewing}
        specialistHome={specialistHome}
        onDecision={handleDraftDecision}
        onLoad={load}
      />
    </div>
  )
}
