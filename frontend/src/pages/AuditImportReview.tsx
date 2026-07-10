import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Loader2,
  ShieldCheck,
} from 'lucide-react'
import {
  auditsApi,
  externalAuditImportsApi,
  getApiErrorMessage,
  type AuditRunDetail,
  type ExternalAuditImportDraft,
  type ExternalAuditImportJob,
  type ExternalAuditPromotionReconciliation,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { DraftFindingsList } from '../components/audit-import/DraftFindingsList'
import { DownstreamWorkflowProof } from '../components/audit-import/DownstreamWorkflowProof'
import { ImportReviewAuditSummary } from '../components/audit-import/ImportReviewAuditSummary'
import { ImportReviewEvidenceCard } from '../components/audit-import/ImportReviewEvidenceCard'
import { ImportReviewOverview } from '../components/audit-import/ImportReviewOverview'

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
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">External Audit Review</h1>
          <h2 className="sr-only">Import review workspace</h2>
          <p className="mt-1 text-muted-foreground">
            OCR and analysis stay in draft until you approve promotion into completed governance
            outcomes.
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={() => void handleBulkApprove()}
            disabled={!job || pendingDraftCount === 0 || isBulkReviewing || isPromoting}
          >
            {isBulkReviewing ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            Approve All Pending
          </Button>
          <Button variant="outline" onClick={() => navigate(specialistHomePath)} disabled={!job}>
            <FileText size={16} />
            {specialistHome.label}
          </Button>
          <Button
            onClick={handlePromoteClick}
            disabled={
              promoteableCount === 0 ||
              isPromoting ||
              job?.status === 'completed' ||
              job?.status === 'promoting'
            }
          >
            {isPromoting ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <ShieldCheck size={16} />
            )}
            Promote Accepted Drafts
          </Button>
        </div>
      </div>

      {promoteableCount > 0 && job?.status === 'review_required' && !showPromoteConfirm ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-900/20 p-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-600" />
            <p className="text-sm text-amber-800 dark:text-amber-200">
              <strong>{promoteableCount}</strong> accepted finding(s) ready for promotion.
              Click <strong>Promote</strong> to write them into the live governance system (actions, risk register, audit records).
            </p>
          </div>
          <Button size="sm" onClick={handlePromoteClick} disabled={isPromoting}>
            {isPromoting ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
            Promote Now
          </Button>
        </div>
      ) : null}

      {showPromoteConfirm ? (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="flex items-center justify-between gap-3 p-5">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Confirm promotion of {promoteableCount} accepted finding(s)?
                </p>
                <p className="text-xs text-muted-foreground">
                  This will create {promoteableCount} finding(s), {acceptedActionCandidates} corrective action(s),{' '}
                  {acceptedRiskCandidates} risk escalation(s), and {acceptedClauseCount} evidence link(s) in the
                  live governance system. This action cannot be undone.
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowPromoteConfirm(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={() => void handlePromoteConfirm()}>
                Confirm Promote
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {successMessage ? (
        <Card className="border-emerald-300 bg-emerald-50" role="alert">
          <CardContent className="flex items-center justify-between gap-3 p-5">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              <p className="text-sm text-emerald-800">{successMessage}</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => setSuccessMessage(null)}>
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

      {reconciliation ? (
        <DownstreamWorkflowProof
          reconciliation={reconciliation}
          onNavigate={(path) => navigate(path)}
        />
      ) : null}

      {error ? (
        <Card className="border-destructive/30 bg-destructive/5" role="alert">
          <CardContent className="space-y-3 p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <p className="text-sm text-destructive">{error}</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => void load()}>
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
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleRetryQueue()}
                disabled={isQueueing}
              >
                {isQueueing ? <Loader2 size={16} className="animate-spin" /> : null}
                Retry Queue
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

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

      {isProcessing ? (
        <Card className="border-primary/30 bg-primary/5" aria-busy="true" role="status">
          <CardContent className="flex items-center gap-4 p-6">
            <Loader2 size={24} className="animate-spin text-primary" />
            <div>
              <p className="font-medium text-foreground">
                Processing import&hellip;
              </p>
              <p className="text-sm text-muted-foreground">
                Extracting text, running dual AI analysis (Mistral + Gemini), and generating draft
                findings. This may take up to five minutes for large documents.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {job &&
      !isProcessing &&
      (job.status === 'pending' ||
        job.status === 'queued' ||
        job.error_code === 'QUEUE_DISPATCH_FAILED') ? (
        <Card className="border-warning/30 bg-warning/5">
          <CardHeader>
            <CardTitle className="text-base">Processing queue</CardTitle>
            <CardDescription>
              This intake exists, but OCR and analysis are not currently running.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-foreground">
              {job.error_code === 'QUEUE_DISPATCH_FAILED'
                ? job.error_detail || 'Background processing could not be started automatically.'
                : 'Retry queueing this import to continue OCR, schema mapping, and reviewer draft generation.'}
            </p>
            <Button onClick={() => void handleRetryQueue()} disabled={isQueueing || isProcessing}>
              {isQueueing ? <Loader2 size={16} className="animate-spin" /> : null}
              Retry Queue
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {job?.processing_warnings_json?.length ? (
        <Card className="border-warning/30 bg-warning/5">
          <CardHeader>
            <CardTitle className="text-base">Reviewer warnings</CardTitle>
            <CardDescription>
              {job.processing_warnings_json.length} item(s) should be checked before promotion.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {job.processing_warnings_json.map((warning, index) => {
              const text = typeof warning === 'string' ? warning : String((warning as Record<string, unknown>)?.text ?? warning)
              const isVisual = text.startsWith('Visual:')
              const isScore = text.toLowerCase().includes('score')
              const isOutcome = text.toLowerCase().includes('outcome') || text.toLowerCase().includes('disagreement')
              return (
                <div
                  key={`warning-${index}`}
                  className={`flex items-start gap-2 rounded px-3 py-2 text-sm ${
                    isOutcome
                      ? 'bg-red-50 border-l-2 border-red-400 text-red-800'
                      : isScore
                        ? 'bg-amber-50 border-l-2 border-amber-400 text-amber-800'
                        : isVisual
                          ? 'bg-blue-50 border-l-2 border-blue-400 text-blue-800'
                          : 'text-foreground'
                  }`}
                >
                  <span className="mt-0.5 text-xs">
                    {isOutcome ? '!' : isScore ? '#' : isVisual ? '\u25CB' : '\u2022'}
                  </span>
                  <span>{text}</span>
                </div>
              )
            })}
          </CardContent>
        </Card>
      ) : null}

      {job?.status === 'failed' ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-base">Import failed</CardTitle>
            <CardDescription>The import did not reach reviewer-ready status.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-destructive">
            <p>{job.error_code || 'IMPORT_FAILED'}</p>
            <p>{job.error_detail || 'Review logs and retry the import job.'}</p>
          </CardContent>
        </Card>
      ) : null}

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

