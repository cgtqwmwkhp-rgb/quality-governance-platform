import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  externalAuditImportsApi,
  getApiErrorMessage,
  type ExternalAuditPromotionReconciliation,
} from '../api/client'
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

import {
  describePromotionFailure,
  describeReconciliationFailure,
  extractPromotionFailedDrafts,
} from '../components/audit-import/importReviewHelpers'
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

  const [busyDraftId, setBusyDraftId] = useState<number | null>(null)
  const [isBulkReviewing, setIsBulkReviewing] = useState(false)
  const [isPromoting, setIsPromoting] = useState(false)
  const [isQueueing, setIsQueueing] = useState(false)
  const [showPromoteConfirm, setShowPromoteConfirm] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

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

  const handleDraftDecision = async (
    draftId: number,
    status: 'accepted' | 'rejected' | 'draft',
    extras?: Record<string, string>,
  ) => {
    setBusyDraftId(draftId)
    setError(null)
    setSuccessMessage(null)
    try {
      const payload: {
        status: 'accepted' | 'rejected' | 'draft'
        title?: string
        description?: string
        severity?: string
        review_notes?: string
      } = { status }
      if (extras) {
        if (extras.title) payload.title = extras.title
        if (extras.description) payload.description = extras.description
        if (extras.severity) payload.severity = extras.severity
        if (extras.review_notes) payload.review_notes = extras.review_notes
      }
      const res = await externalAuditImportsApi.reviewDraft(draftId, payload)
      setDrafts((prev) => prev.map((draft) => (draft.id === draftId ? res.data : draft)))
      setError(null)
    } catch (err) {
      console.error('Failed to update draft review decision', err)
      setError('Failed to update the draft. Please retry.')
    } finally {
      setBusyDraftId(null)
    }
  }

  const handlePromoteClick = () => {
    if (!job || promoteableCount === 0 || ['completed', 'promoting'].includes(job.status)) return
    setShowPromoteConfirm(true)
  }

  const handleBulkApprove = async () => {
    if (!job || pendingDraftCount === 0) return
    setIsBulkReviewing(true)
    setError(null)
    setSuccessMessage(null)
    try {
      const res = await externalAuditImportsApi.bulkReviewJob(job.id, { status: 'accepted' })
      setDrafts(res.data)
      setSuccessMessage(`Approved ${pendingDraftCount} pending finding(s). Review and promote when ready.`)
      await load()
    } catch (err) {
      console.error('Failed to bulk approve draft findings', err)
      setError(getApiErrorMessage(err) || 'Failed to approve all pending findings. Please retry.')
    } finally {
      setIsBulkReviewing(false)
    }
  }

  const handlePromoteConfirm = async () => {
    if (!job) return
    setShowPromoteConfirm(false)
    setIsPromoting(true)
    setError(null)
    setPromotionFailedDrafts(null)
    setSuccessMessage(null)
    try {
      const promoteRes = await externalAuditImportsApi.promoteJob(job.id)
      await load()
      let nextReconciliation: ExternalAuditPromotionReconciliation | null = null
      try {
        const reconciliationRes = await externalAuditImportsApi.getReconciliation(job.id)
        nextReconciliation = reconciliationRes.data
        setReconciliationNotice(null)
      } catch (reconciliationErr) {
        setReconciliationNotice(describeReconciliationFailure(reconciliationErr, 'completed') || null)
      }
      setReconciliation(nextReconciliation)
      if (nextReconciliation?.failed_total) {
        setSuccessMessage(
          `Promotion partially completed: ${nextReconciliation.promoted_total} finding(s) materialized, ${nextReconciliation.failed_total} still require review.`,
        )
      } else {
        const promotedFromSummary = promoteRes.data.promotion_summary_json?.[
          'promoted_findings'
        ] as unknown
        const promotedCount =
          nextReconciliation?.promoted_total ??
          (Array.isArray(promotedFromSummary) ? promotedFromSummary.length : promoteableCount)
        setSuccessMessage(
          `Successfully promoted ${promotedCount} finding(s) into the live governance system.`,
        )
      }
    } catch (err) {
      console.error('Failed to promote imported audit findings', err)
      setPromotionFailedDrafts(extractPromotionFailedDrafts(err))
      setError(describePromotionFailure(err))
    } finally {
      setIsPromoting(false)
    }
  }

  const handleRetryQueue = async () => {
    if (!job) return
    setIsQueueing(true)
    setError(null)
    try {
      const queueRes = await externalAuditImportsApi.queueJob(job.id)
      setQueueNotice(null)
      setJob(queueRes.data)

      if (queueRes.data.status === 'queued') {
        setIsProcessing(true)
        try {
          await externalAuditImportsApi.processJob(job.id)
        } catch (processErr) {
          console.error('Import processing failed after retry', processErr)
        } finally {
          setIsProcessing(false)
        }
      }
      await load()
    } catch (err) {
      console.error('Failed to queue external audit import job', err)
      setError('Failed to start processing. Please retry queueing the import.')
    } finally {
      setIsQueueing(false)
    }
  }

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
        onDismissSuccess={() => setSuccessMessage(null)}
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
        onDismissSuccess={() => setSuccessMessage(null)}
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
