import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  auditsApi,
  externalAuditImportsApi,
  getApiErrorMessage,
  type AuditRunDetail,
  type ExternalAuditImportDraft,
  type ExternalAuditImportJob,
  type ExternalAuditPromotionReconciliation,
} from '../api/client'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { DraftFindingsList } from '../components/audit-import/DraftFindingsList'
import { DownstreamWorkflowProof } from '../components/audit-import/DownstreamWorkflowProof'
import { ImportReviewAuditSummary } from '../components/audit-import/ImportReviewAuditSummary'
import { ImportReviewEvidenceCard } from '../components/audit-import/ImportReviewEvidenceCard'
import { ImportReviewHeader } from '../components/audit-import/ImportReviewHeader'
import { ImportReviewNotices } from '../components/audit-import/ImportReviewNotices'
import { ImportReviewOverview } from '../components/audit-import/ImportReviewOverview'
import { ImportReviewProcessingPanels } from '../components/audit-import/ImportReviewProcessingPanels'
import { ImportReviewPromoteBanner } from '../components/audit-import/ImportReviewPromoteBanner'

import {
  ACTION_FINDING_TYPES,
  describePromotionFailure,
  describeReconciliationFailure,
  deriveDeclaredProgramLabel,
  deriveSpecialistHome,
  extractPromotionFailedDrafts,
  readProvenanceNumber,
  readProvenanceString,
  type PromotionFailedDraftRow,
} from '../components/audit-import/importReviewHelpers'

export default function AuditImportReview() {
  const { auditId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const jobId = Number(searchParams.get('jobId') || '')
  const routeAuditId = Number(auditId || '')

  const [job, setJob] = useState<ExternalAuditImportJob | null>(null)
  const [auditRun, setAuditRun] = useState<AuditRunDetail | null>(null)
  const [drafts, setDrafts] = useState<ExternalAuditImportDraft[]>([])
  const [reconciliation, setReconciliation] = useState<ExternalAuditPromotionReconciliation | null>(null)
  const [loading, setLoading] = useState(true)
  const initialLoadDone = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [queueNotice, setQueueNotice] = useState<string | null>(
    searchParams.get('queueError') === '1'
      ? 'The import workspace is ready, but automatic processing did not start. Retry queueing below.'
      : null,
  )
  const [busyDraftId, setBusyDraftId] = useState<number | null>(null)
  const [isBulkReviewing, setIsBulkReviewing] = useState(false)
  const [isPromoting, setIsPromoting] = useState(false)
  const [isQueueing, setIsQueueing] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [showPromoteConfirm, setShowPromoteConfirm] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [promotionFailedDrafts, setPromotionFailedDrafts] = useState<PromotionFailedDraftRow[] | null>(null)
  const [reconciliationNotice, setReconciliationNotice] = useState<string | null>(null)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null)
  const [isDocumentHidden, setIsDocumentHidden] = useState(
    () => typeof document !== 'undefined' && document.hidden,
  )
  const processingTriggered = useRef(false)
  const pollDelayMs = useRef(5000)

  const load = useCallback(async () => {
    if (!jobId && (!Number.isFinite(routeAuditId) || routeAuditId <= 0)) {
      setJob(null)
      setAuditRun(null)
      setDrafts([])
      setError('Missing import job reference.')
      setLoading(false)
      initialLoadDone.current = true
      return
    }

    if (!initialLoadDone.current) {
      setLoading(true)
    }
    setError(null)
    setPromotionFailedDrafts(null)
    setReconciliationNotice(null)
    try {
      let resolvedJobRes = null
      if (jobId) {
        resolvedJobRes = await externalAuditImportsApi.getJob(jobId)
      } else if (Number.isFinite(routeAuditId) && routeAuditId > 0) {
        resolvedJobRes = await externalAuditImportsApi.getLatestJobForRun(routeAuditId)
      }

      if (!resolvedJobRes) {
        throw new Error('Import job could not be resolved')
      }

      const [jobRes, draftsRes, reconciliationResult] = await Promise.all([
        Promise.resolve(resolvedJobRes),
        externalAuditImportsApi.listDrafts(resolvedJobRes.data.id),
        externalAuditImportsApi
          .getReconciliation(resolvedJobRes.data.id)
          .then((res) => ({ data: res.data, notice: null }))
          .catch((reconciliationErr) => ({
            data: null,
            notice: describeReconciliationFailure(reconciliationErr, resolvedJobRes.data.status) || null,
          })),
      ])
      if (
        Number.isFinite(routeAuditId) &&
        routeAuditId > 0 &&
        jobRes.data.audit_run_id !== routeAuditId
      ) {
        setJob(null)
        setAuditRun(null)
        setDrafts([])
        setError(
          'This import job belongs to a different audit run. Re-open it from the audits workspace.',
        )
        return
      }
      let auditRunDetail: AuditRunDetail | null = null
      try {
        const auditRunRes = await auditsApi.getRunDetail(jobRes.data.audit_run_id)
        auditRunDetail = auditRunRes.data
      } catch (auditRunErr) {
        console.error('Failed to load resolved audit run details for import review', auditRunErr)
      }
      setJob(jobRes.data)
      setAuditRun(auditRunDetail)
      setDrafts(draftsRes.data)
      setReconciliation(reconciliationResult.data)
      setReconciliationNotice(reconciliationResult.notice)
      setPromotionFailedDrafts(null)
      setLastUpdatedAt(new Date())
    } catch (err) {
      console.error('Failed to load external audit review workspace', err)
      setAuditRun(null)
      setReconciliation(null)
      setReconciliationNotice(null)
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404 && !jobId) {
        setError(
          'No import job has been created for this audit yet. Attach a source report and queue the import first.',
        )
      } else if (status === 422) {
        setError(getApiErrorMessage(err))
      } else {
        setError('Failed to load the import review workspace. Please retry.')
      }
    } finally {
      setLoading(false)
      initialLoadDone.current = true
    }
  }, [jobId, routeAuditId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const onVisibilityChange = () => {
      setIsDocumentHidden(document.hidden)
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [])

  useEffect(() => {
    if (!job || job.status !== 'queued' || isProcessing || processingTriggered.current) return
    processingTriggered.current = true
    setIsProcessing(true)
    externalAuditImportsApi
      .processJob(job.id)
      .then(() => load())
      .catch((err) => {
        console.error('Import processing failed', err)
        void load()
      })
      .finally(() => setIsProcessing(false))
  }, [job, isProcessing, load])

  useEffect(() => {
    if (!job || !['processing', 'promoting'].includes(job.status)) {
      pollDelayMs.current = 5000
      return
    }
    if (isDocumentHidden) return

    const delay = pollDelayMs.current
    const timeoutId = window.setTimeout(() => {
      void load().finally(() => {
        pollDelayMs.current = Math.min(pollDelayMs.current * 2, 30000)
      })
    }, delay)
    return () => window.clearTimeout(timeoutId)
  }, [job, load, isDocumentHidden])

  const approvedCount = useMemo(
    () =>
      drafts.filter((draft) => draft.status === 'accepted' || draft.status === 'promoted').length,
    [drafts],
  )
  const promoteableCount = useMemo(
    () =>
      drafts.filter((draft) => draft.status === 'accepted' && !draft.promoted_finding_id).length,
    [drafts],
  )
  const pendingDraftCount = useMemo(
    () => drafts.filter((draft) => draft.status === 'draft' && !draft.promoted_finding_id).length,
    [drafts],
  )
  const acceptedDrafts = useMemo(
    () => drafts.filter((draft) => draft.status === 'accepted' || draft.status === 'promoted'),
    [drafts],
  )
  const acceptedClauseCount = useMemo(() => {
    const clauseKeys = new Set<string>()
    acceptedDrafts.forEach((draft) => {
      draft.mapped_standards_json?.forEach((mapping) => {
        const clauseKey =
          typeof mapping?.clause_id === 'string'
            ? mapping.clause_id
            : [mapping?.standard, mapping?.clause_number].filter(Boolean).join(':')
        if (clauseKey) clauseKeys.add(clauseKey)
      })
    })
    return clauseKeys.size
  }, [acceptedDrafts])
  const acceptedActionCandidates = useMemo(
    () =>
      acceptedDrafts.filter((draft) => ACTION_FINDING_TYPES.includes(draft.finding_type)).length,
    [acceptedDrafts],
  )
  const acceptedRiskCandidates = useMemo(
    () =>
      acceptedDrafts.filter(
        (draft) => ACTION_FINDING_TYPES.includes(draft.finding_type) && ['medium', 'high', 'critical'].includes(draft.severity),
      ).length,
    [acceptedDrafts],
  )
  const promotionSummary = job?.promotion_summary_json ?? null
  const schemeAlignment = promotionSummary?.scheme_alignment as Record<string, unknown> | undefined
  const declaredProgramLabel = deriveDeclaredProgramLabel(auditRun, job)
  const declaredSourceOrigin =
    auditRun?.source_origin || readProvenanceString(job, 'declared_source_origin')
  const declaredScheme =
    auditRun?.assurance_scheme || readProvenanceString(job, 'declared_assurance_scheme')
  const resolvedTemplateVersion =
    auditRun?.template_version ?? readProvenanceNumber(job, 'processing_template_version')
  const resolvedTemplateId =
    auditRun?.template_id ?? readProvenanceNumber(job, 'processing_template_id')
  const resolvedTemplateName = auditRun?.template_name
  const declaredExternalBody =
    auditRun?.external_body_name || readProvenanceString(job, 'declared_external_body_name')
  const declaredExternalReference =
    auditRun?.external_reference || readProvenanceString(job, 'declared_external_reference')
  const specialistHome = useMemo(() => deriveSpecialistHome(job), [job])
  const specialistHomePath =
    reconciliation?.view_links?.specialist_home || reconciliation?.view_links?.uvdb || specialistHome.path

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

  if (loading) {
    return (
      <div className="p-6">
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

      {reconciliation ? (
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
