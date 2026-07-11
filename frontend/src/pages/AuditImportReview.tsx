import { AlertCircle } from 'lucide-react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ImportReviewBody } from '../components/audit-import/ImportReviewBody'
import { ImportReviewHeader } from '../components/audit-import/ImportReviewHeader'
import { ImportReviewLoadingState } from '../components/audit-import/ImportReviewLoadingState'
import { useImportReviewActions } from '../components/audit-import/useImportReviewActions'
import { useImportReviewDerived } from '../components/audit-import/useImportReviewDerived'
import { useImportReviewLoader } from '../components/audit-import/useImportReviewLoader'
import { UpstreamDegradedBanner } from '../components/UpstreamDegradedBanner'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'

/** Next-step copy when the import workspace cannot load a job. */
export function resolveImportUnavailableNextStep(error: string): string {
  if (error.includes('different audit run')) {
    return 'Next: Open the audits workspace and launch Import Review from the correct audit run.'
  }
  if (error.includes('No import job has been created')) {
    return 'Next: Attach a source report on the audit, queue the import, then return here.'
  }
  if (error.includes('Missing import job reference')) {
    return 'Next: Open Import Review from an audit run that already has an import job.'
  }
  return 'Next: Retry loading this workspace. If it still fails, reopen Import Review from the audits list.'
}

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

  // Blocking empty/error: no job loaded — surface clear next-step CTAs instead of
  // empty review chrome with a disabled specialist-home button (Preferred CUJ).
  if (!job && error) {
    const nextStep = resolveImportUnavailableNextStep(error)
    return (
      <div className="space-y-6 p-6 animate-fade-in">
        <div>
          <h1 className="text-3xl font-bold text-foreground">External Audit Review</h1>
          <h2 className="sr-only">Import review workspace</h2>
          <p className="mt-1 text-muted-foreground">
            OCR and analysis stay in draft until you approve promotion into completed governance
            outcomes.
          </p>
        </div>

        <Card
          className="border-destructive/30 bg-destructive/5"
          role="alert"
          data-testid="import-review-workspace-unavailable"
        >
          <CardContent className="space-y-4 p-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" aria-hidden />
              <div>
                <p className="text-sm font-medium text-foreground">Import review unavailable</p>
                <p className="mt-1 text-sm text-destructive">{error}</p>
                <p className="mt-2 text-sm text-muted-foreground">{nextStep}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => void load()}>Retry</Button>
              <Button variant="outline" onClick={() => navigate(specialistHomePath)}>
                {specialistHome.label}
              </Button>
            </div>
          </CardContent>
        </Card>
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
        isProcessing={isProcessing}
        hasJob={Boolean(job)}
        jobStatus={job?.status}
        specialistHomeLabel={specialistHome.label}
        onBulkApprove={() => void handleBulkApprove()}
        onOpenSpecialistHome={() => navigate(specialistHomePath)}
        onPromoteClick={handlePromoteClick}
      />

      <UpstreamDegradedBanner pollReadyz />

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
