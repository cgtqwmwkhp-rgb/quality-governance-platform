import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ImportReviewBody } from '../components/audit-import/ImportReviewBody'
import { ImportReviewHeader } from '../components/audit-import/ImportReviewHeader'
import { ImportReviewLoadingState } from '../components/audit-import/ImportReviewLoadingState'
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
      <ImportReviewLoadingState
        specialistHomeLabel={specialistHome.label}
        onOpenSpecialistHome={() => navigate(specialistHomePath)}
      />
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

      <ImportReviewBody
        navigate={navigate}
        job={job}
        drafts={drafts}
        reconciliation={reconciliation}
        error={error}
        queueNotice={queueNotice}
        reconciliationNotice={reconciliationNotice}
        promotionFailedDrafts={promotionFailedDrafts}
        lastUpdatedAt={lastUpdatedAt}
        isProcessing={isProcessing}
        isDocumentHidden={isDocumentHidden}
        load={load}
        approvedCount={approvedCount}
        promoteableCount={promoteableCount}
        acceptedClauseCount={acceptedClauseCount}
        acceptedActionCandidates={acceptedActionCandidates}
        acceptedRiskCandidates={acceptedRiskCandidates}
        schemeAlignment={schemeAlignment}
        declaredProgramLabel={declaredProgramLabel}
        declaredSourceOrigin={declaredSourceOrigin}
        declaredScheme={declaredScheme}
        resolvedTemplateVersion={resolvedTemplateVersion}
        resolvedTemplateId={resolvedTemplateId}
        resolvedTemplateName={resolvedTemplateName}
        declaredExternalBody={declaredExternalBody}
        declaredExternalReference={declaredExternalReference}
        specialistHome={specialistHome}
        busyDraftId={busyDraftId}
        isBulkReviewing={isBulkReviewing}
        isPromoting={isPromoting}
        isQueueing={isQueueing}
        showPromoteConfirm={showPromoteConfirm}
        setShowPromoteConfirm={setShowPromoteConfirm}
        successMessage={successMessage}
        dismissSuccess={dismissSuccess}
        handleDraftDecision={handleDraftDecision}
        handlePromoteClick={handlePromoteClick}
        handlePromoteConfirm={handlePromoteConfirm}
        handleRetryQueue={handleRetryQueue}
      />
    </div>
  )
}
