import type { NavigateFunction } from 'react-router-dom'
import { DraftFindingsList } from './DraftFindingsList'
import {
  DownstreamWorkflowProof,
  isCompleteReconciliation,
} from './DownstreamWorkflowProof'
import { ImportReviewAuditSummary } from './ImportReviewAuditSummary'
import { ImportReviewEvidenceCard } from './ImportReviewEvidenceCard'
import { ImportReviewNotices } from './ImportReviewNotices'
import { ImportReviewOverview } from './ImportReviewOverview'
import { ImportReviewProcessingPanels } from './ImportReviewProcessingPanels'
import { ImportReviewPromoteBanner } from './ImportReviewPromoteBanner'
import type { useImportReviewActions } from './useImportReviewActions'
import type { useImportReviewDerived } from './useImportReviewDerived'
import type { useImportReviewLoader } from './useImportReviewLoader'

type Loader = ReturnType<typeof useImportReviewLoader>
type Derived = ReturnType<typeof useImportReviewDerived>
type Actions = ReturnType<typeof useImportReviewActions>

type ImportReviewBodyProps = {
  navigate: NavigateFunction
  job: Loader['job']
  drafts: Loader['drafts']
  reconciliation: Loader['reconciliation']
  error: Loader['error']
  queueNotice: Loader['queueNotice']
  reconciliationNotice: Loader['reconciliationNotice']
  promotionFailedDrafts: Loader['promotionFailedDrafts']
  lastUpdatedAt: Loader['lastUpdatedAt']
  isProcessing: Loader['isProcessing']
  isDocumentHidden: Loader['isDocumentHidden']
  load: Loader['load']
  approvedCount: Derived['approvedCount']
  promoteableCount: Derived['promoteableCount']
  acceptedClauseCount: Derived['acceptedClauseCount']
  acceptedActionCandidates: Derived['acceptedActionCandidates']
  acceptedRiskCandidates: Derived['acceptedRiskCandidates']
  schemeAlignment: Derived['schemeAlignment']
  declaredProgramLabel: Derived['declaredProgramLabel']
  declaredSourceOrigin: Derived['declaredSourceOrigin']
  declaredScheme: Derived['declaredScheme']
  resolvedTemplateVersion: Derived['resolvedTemplateVersion']
  resolvedTemplateId: Derived['resolvedTemplateId']
  resolvedTemplateName: Derived['resolvedTemplateName']
  declaredExternalBody: Derived['declaredExternalBody']
  declaredExternalReference: Derived['declaredExternalReference']
  specialistHome: Derived['specialistHome']
  busyDraftId: Actions['busyDraftId']
  isBulkReviewing: Actions['isBulkReviewing']
  isPromoting: Actions['isPromoting']
  isQueueing: Actions['isQueueing']
  showPromoteConfirm: Actions['showPromoteConfirm']
  setShowPromoteConfirm: Actions['setShowPromoteConfirm']
  successMessage: Actions['successMessage']
  dismissSuccess: Actions['dismissSuccess']
  handleDraftDecision: Actions['handleDraftDecision']
  handlePromoteClick: Actions['handlePromoteClick']
  handlePromoteConfirm: Actions['handlePromoteConfirm']
  handleRetryQueue: Actions['handleRetryQueue']
}

export function ImportReviewBody(props: ImportReviewBodyProps) {
  const {
    navigate,
    job,
    drafts,
    reconciliation,
    error,
    queueNotice,
    reconciliationNotice,
    promotionFailedDrafts,
    lastUpdatedAt,
    isProcessing,
    isDocumentHidden,
    load,
    approvedCount,
    promoteableCount,
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
    handlePromoteConfirm,
    handleRetryQueue,
  } = props

  return (
    <>
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
    </>
  )
}
