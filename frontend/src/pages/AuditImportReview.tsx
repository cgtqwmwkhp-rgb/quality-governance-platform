import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  Building2,
  CheckCircle2,
  FileText,
  Loader2,
  ShieldCheck,
  User,
} from 'lucide-react'
import {
  auditsApi,
  createApiError,
  ErrorClass,
  externalAuditImportsApi,
  getApiErrorMessage,
  type AuditRunDetail,
  type ExternalAuditImportDraft,
  type ExternalAuditImportJob,
  type ExternalAuditPromotionReconciliation,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { DraftFindingsList } from '../components/audit-import/DraftFindingsList'

const ACTION_FINDING_TYPES = [
  'nonconformity',
  'major_nonconformity',
  'minor_nonconformity',
  'competence_gap',
  'finding',
  'flagged_item',
  'question_answered_no',
]

function humanizeLabel(value: string | null | undefined) {
  if (!value) return ''
  return value.replace(/_/g, ' ')
}

function formatDate(value: string | null | undefined): string {
  if (!value) return ''
  try {
    return new Intl.DateTimeFormat('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(new Date(value))
  } catch {
    return String(value)
  }
}

function describeReconciliationFailure(error: unknown, jobStatus?: string): string {
  const apiError = createApiError(error)
  if (apiError.error_class === ErrorClass.NOT_FOUND) {
    if (!jobStatus || !['completed', 'promoting'].includes(jobStatus)) {
      return ''
    }
    return 'Downstream workflow diagnostics are unavailable for this job on the current backend.'
  }
  if (apiError.error_class === ErrorClass.VALIDATION_ERROR) {
    return `Downstream workflow diagnostics unavailable: ${getApiErrorMessage(error)}`
  }
  if (apiError.error_class === ErrorClass.SERVER_ERROR) {
    return 'Downstream workflow diagnostics are temporarily unavailable while the backend recovers.'
  }
  return 'Downstream workflow diagnostics could not be loaded right now.'
}

function describePromotionFailure(error: unknown): string {
  const apiError = createApiError(error)
  if (apiError.error_class === ErrorClass.VALIDATION_ERROR) {
    return getApiErrorMessage(error)
  }
  if (apiError.error_class === ErrorClass.SERVER_ERROR) {
    return 'Promotion is temporarily unavailable while the backend recovers. Please retry shortly.'
  }
  return 'Promotion failed. Review the accepted drafts and try again.'
}

type PromotionFailedDraftRow = {
  draft_id?: number
  title?: string
  error?: string
  error_type?: string
}

/** Server returns failed_drafts inside error.details on 422 when materialization fails. */
function extractPromotionFailedDrafts(err: unknown): PromotionFailedDraftRow[] | null {
  if (!axios.isAxiosError(err) || err.response?.status !== 422) return null
  const data = err.response?.data as { error?: { details?: { failed_drafts?: unknown } } } | undefined
  const raw = data?.error?.details?.failed_drafts
  if (!Array.isArray(raw) || raw.length === 0) return null
  return raw.slice(0, 20).map((row: Record<string, unknown>) => ({
    draft_id: typeof row.draft_id === 'number' ? row.draft_id : undefined,
    title: typeof row.title === 'string' ? row.title : undefined,
    error: typeof row.error === 'string' ? row.error : undefined,
    error_type: typeof row.error_type === 'string' ? row.error_type : undefined,
  }))
}

function readProvenanceString(job: ExternalAuditImportJob | null, key: string) {
  const value = job?.provenance_json?.[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function readProvenanceNumber(job: ExternalAuditImportJob | null, key: string) {
  const value = job?.provenance_json?.[key]
  return typeof value === 'number' ? value : null
}

function deriveDeclaredProgramLabel(
  auditRun: AuditRunDetail | null,
  job: ExternalAuditImportJob | null,
) {
  const declaredScheme =
    auditRun?.assurance_scheme || readProvenanceString(job, 'declared_assurance_scheme') || ''
  const normalizedScheme = declaredScheme.toLowerCase()
  const declaredSource =
    auditRun?.source_origin || readProvenanceString(job, 'declared_source_origin') || ''

  if (normalizedScheme.includes('achilles') || normalizedScheme.includes('uvdb')) {
    return 'Achilles / UVDB'
  }
  if (normalizedScheme.includes('planet mark')) {
    return 'Planet Mark'
  }
  if (declaredSource === 'customer') {
    return 'Customer Audit'
  }
  if (declaredSource === 'certification' && normalizedScheme.startsWith('iso')) {
    return 'ISO Audit'
  }
  if (declaredScheme) {
    return declaredScheme
  }
  if (declaredSource) {
    return humanizeLabel(declaredSource)
  }
  return 'External Audit'
}

function deriveSpecialistHome(job: ExternalAuditImportJob | null): { path: string; label: string } {
  const path = job?.specialist_home_path?.trim()
  const label = job?.specialist_home_label?.trim()
  if (path && label) {
    return { path, label }
  }

  let scheme = (job?.detected_scheme || '').trim().toLowerCase()
  if (!scheme) {
    const provenance = job?.provenance_json || {}
    const declaredScheme = String(provenance.declared_assurance_scheme || '').toLowerCase()
    const declaredSource = String(provenance.declared_source_origin || '').toLowerCase()
    if (declaredScheme.includes('achilles') || declaredScheme.includes('uvdb')) {
      scheme = 'achilles_uvdb'
    } else if (declaredScheme.includes('planet mark')) {
      scheme = 'planet_mark'
    } else if (declaredScheme.startsWith('iso')) {
      scheme = 'iso'
    } else if (declaredSource === 'customer') {
      scheme = 'customer_other'
    }
  }

  if (scheme === 'achilles_uvdb') {
    return { path: '/uvdb', label: 'Open Achilles / UVDB' }
  }
  if (scheme === 'planet_mark') {
    return { path: '/planet-mark', label: 'Open Planet Mark' }
  }
  if (scheme === 'iso') {
    return { path: '/compliance', label: 'Open ISO Compliance' }
  }
  if (scheme === 'customer_other' || scheme === 'other') {
    return { path: '/customer-audits', label: 'Open Customer Audits' }
  }
  return { path: '/customer-audits', label: 'Open Customer Audits' }
}

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
        <Card className="border-border/70">
          <CardHeader>
            <CardTitle className="text-base">Downstream Workflow Proof</CardTitle>
            <CardDescription>
              Canonical read model: {reconciliation.canonical_read_model.replace(/_/g, ' ')}.
              {reconciliation.failed_total > 0
                ? ` ${reconciliation.failed_total} accepted draft(s) still need recovery before the workflow is complete.`
                : ' All downstream workflow steps are traceable from this import.'}{' '}
              UVDB and unified registry rows appear here only after findings materialize; if promotion did not finish,
              sync or registry proof may show as missing—that usually reflects sequencing, not a separate outage.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-lg border border-border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Findings</p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {reconciliation.materialized.audit_findings}
                </p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">CAPA Actions</p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {reconciliation.materialized.capa_actions}
                </p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Enterprise Risks</p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {reconciliation.materialized.enterprise_risks}
                </p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">UVDB Sync</p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {reconciliation.materialized.uvdb_audit_id ? `Row #${reconciliation.materialized.uvdb_audit_id}` : 'Not visible'}
                </p>
              </div>
            </div>

            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              {reconciliation.proof_matrix.map((step) => (
                <div key={step.step} className="rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-foreground">
                      {step.step.replace(/_/g, ' ')}
                    </p>
                    <Badge
                      variant={
                        step.status === 'ok'
                          ? 'success'
                          : step.status === 'partial'
                            ? 'warning'
                            : step.status === 'none' || step.status === 'n/a'
                              ? 'secondary'
                              : 'destructive'
                      }
                    >
                      {step.status}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{step.detail}</p>
                </div>
              ))}
            </div>

            {reconciliation.failed_total > 0 ? (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-4">
                <p className="text-sm font-medium text-amber-800">Accepted drafts still pending recovery</p>
                <div className="mt-2 space-y-1 text-xs text-amber-900">
                  {reconciliation.failed_drafts.map((draft, index) => (
                    <p key={`failed-draft-${index}`}>
                      Draft #{String(draft.draft_id ?? '?')}: {String(draft.title || draft.error || 'Promotion failed')}
                    </p>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              {reconciliation.view_links.actions ? (
                <Button variant="outline" size="sm" onClick={() => navigate(reconciliation.view_links.actions)}>
                  View Audit Actions
                </Button>
              ) : null}
              {reconciliation.view_links.risk_register ? (
                <Button variant="outline" size="sm" onClick={() => navigate(reconciliation.view_links.risk_register)}>
                  View Audit Risks
                </Button>
              ) : null}
              {reconciliation.view_links.uvdb ? (
                <Button variant="outline" size="sm" onClick={() => navigate(reconciliation.view_links.uvdb)}>
                  View UVDB Sync
                </Button>
              ) : null}
            </div>

            {reconciliation.materialized.capa_actions > 0 || reconciliation.materialized.enterprise_risks > 0 ? (
              <div className="mt-4 rounded-lg border border-border/80 bg-muted/30 p-4 text-sm text-muted-foreground">
                <p className="font-medium text-foreground">Governance hand-off after promotion</p>
                <p className="mt-2">
                  CAPA actions from this import are live in <span className="text-foreground">Actions</span> as usual.
                  Enterprise risk suggestions from the same import may appear under{' '}
                  <span className="text-foreground">Risk Register → Import triage</span> until accepted or rejected.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      navigate(
                        reconciliation.view_links.actions || '/actions?sourceType=audit_finding',
                      )
                    }
                  >
                    Open audit-sourced actions
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => navigate('/risk-register?triage=import')}>
                    Open import risk triage
                  </Button>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
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
        <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-primary" />
                {job.reference_number}
              </CardTitle>
              <CardDescription>
                Status: {job.status.replace(/_/g, ' ')}.{' '}
                {job.analysis_summary || 'Analysis summary pending.'}
                {['processing', 'promoting'].includes(job.status) || isProcessing ? (
                  <span className="mt-1 block text-xs">
                    {isProcessing || job.status === 'processing' || job.status === 'promoting'
                      ? 'Processing in progress — this workspace refreshes automatically.'
                      : null}
                    {lastUpdatedAt
                      ? ` Last updated ${new Intl.DateTimeFormat('en-GB', {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        }).format(lastUpdatedAt)}.`
                      : ''}
                    {isDocumentHidden ? ' Updates paused while this tab is hidden.' : ''}
                  </span>
                ) : lastUpdatedAt ? (
                  <span className="mt-1 block text-xs">
                    Last updated{' '}
                    {new Intl.DateTimeFormat('en-GB', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    }).format(lastUpdatedAt)}
                    .
                  </span>
                ) : null}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Declared intake
                </p>
                <p className="mt-1 font-medium text-foreground">{declaredProgramLabel}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {declaredSourceOrigin
                    ? `Source: ${humanizeLabel(declaredSourceOrigin)}`
                    : 'Source pending'}
                  {declaredScheme ? ` · Scheme: ${declaredScheme}` : ''}
                </p>
              </div>
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Processing template
                </p>
                <p className="mt-1 font-medium text-foreground">
                  {(() => {
                    const raw = resolvedTemplateName || ''
                    if (raw.startsWith('ZZZ') || raw.includes('(System)')) {
                      const schemeLabel = job.detected_scheme || ''
                      return schemeLabel ? `${schemeLabel} Intake` : 'External Audit Intake'
                    }
                    return raw || (resolvedTemplateId ? `Template ${resolvedTemplateId}` : 'Pending resolution')
                  })()}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {resolvedTemplateVersion != null
                    ? `Version ${resolvedTemplateVersion}`
                    : 'Version pending'}
                </p>
              </div>
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Source file</p>
                <p className="mt-1 font-medium text-foreground">
                  {job.source_filename || 'Source document'}
                </p>
                {(declaredExternalBody || declaredExternalReference) && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {[declaredExternalBody, declaredExternalReference].filter(Boolean).join(' · ')}
                  </p>
                )}
              </div>
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Extraction</p>
                <p className="mt-1 font-medium text-foreground">
                  {job.extraction_method || 'pending'}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {job.page_count ? `${job.page_count} page(s)` : 'Pages pending'}
                  {job.source_sheet_count ? `, ${job.source_sheet_count} sheet(s)` : ''}
                </p>
              </div>
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Classification
                </p>
                <p className="mt-1 font-medium text-foreground">
                  {humanizeLabel(job.detected_scheme) || 'Pending classification'}
                </p>
                {job.detected_scheme_confidence != null ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {Math.round(job.detected_scheme_confidence * 100)}% confidence
                  </p>
                ) : null}
              </div>
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  OCR provider
                </p>
                <p className="mt-1 font-medium text-foreground">
                  {job.provider_name || 'Pending provider'}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {job.provider_model || 'Model pending'}
                </p>
              </div>
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Review progress
                </p>
                <p className="mt-1 font-medium text-foreground">
                  {approvedCount + drafts.filter((d) => d.status === 'rejected').length} / {drafts.length} reviewed
                </p>
                {drafts.length > 0 ? (
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all"
                      style={{
                        width: `${Math.round(((approvedCount + drafts.filter((d) => d.status === 'rejected').length) / drafts.length) * 100)}%`,
                      }}
                    />
                  </div>
                ) : null}
                <p className="mt-1 text-xs text-muted-foreground">
                  {approvedCount} accepted, {drafts.filter((d) => d.status === 'rejected').length} rejected, {promoteableCount} awaiting promotion
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Scorecard</CardTitle>
              <CardDescription>
                Normalized audit interpretation before any live promotion happens.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Outcome</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Badge variant="outline">
                    {job.outcome_status?.replace(/_/g, ' ') || 'review required'}
                  </Badge>
                  {job.scheme_version ? (
                    <Badge variant="secondary">{job.scheme_version}</Badge>
                  ) : null}
                  {job.has_tabular_data ? (
                    <Badge variant="info">Tabular evidence detected</Badge>
                  ) : null}
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Overall score
                  </p>
                  {job.score_percentage != null ? (
                    <>
                      <p className="mt-1 text-2xl font-bold text-foreground">
                        {job.score_percentage.toFixed(1)}%
                      </p>
                      <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full transition-all ${
                            job.score_percentage >= 80
                              ? 'bg-emerald-500'
                              : job.score_percentage >= 50
                                ? 'bg-amber-500'
                                : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.min(job.score_percentage, 100)}%` }}
                        />
                      </div>
                    </>
                  ) : (
                    <p className="mt-1 font-medium text-foreground">No explicit score extracted</p>
                  )}
                  {job.overall_score != null && job.max_score != null ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {job.overall_score} / {job.max_score}
                    </p>
                  ) : null}
                  <p className="mt-1 text-xs text-muted-foreground italic">
                    Weighted composite from audit body — see pillar breakdown below
                  </p>
                </div>
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Issuer</p>
                  <p className="mt-1 font-medium text-foreground">
                    {job.issuer_name || 'Reviewer confirmation required'}
                  </p>
                  {job.report_date ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Report date: {formatDate(job.report_date as unknown as string)}
                    </p>
                  ) : null}
                </div>
              </div>
              {job.score_breakdown_json?.length ? (
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Score breakdown
                  </p>
                  <div className="mt-3 grid gap-2">
                    {job.score_breakdown_json.map((item, index) => {
                      const pct = Number(item.percentage ?? 0)
                      return (
                        <div key={`score-breakdown-${index}`} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-foreground">
                              {String(item.label || `Section ${index + 1}`)}
                            </span>
                            <span className="text-muted-foreground">
                              {String(item.score ?? '-')} / {String(item.max_score ?? '-')} (
                              {String(item.percentage ?? '-')}%)
                            </span>
                          </div>
                          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                            <div
                              className={`h-full rounded-full ${
                                pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500'
                              }`}
                              style={{ width: `${Math.min(pct, 100)}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {(() => {
        const prov = job?.provenance_json ?? {}
        const orgName = String(
          job?.organization_name ?? prov.organization_name ?? prov.declared_organization_name ?? '',
        )
        const auditorName = String(job?.auditor_name ?? prov.auditor_name ?? '')
        const auditType = String(job?.audit_type ?? prov.audit_type ?? '')
        const certNo = String(job?.certificate_number ?? prov.certificate_number ?? '')
        const scope = String(job?.audit_scope ?? prov.audit_scope ?? '')
        const nextDate = String(job?.next_audit_date ?? prov.next_audit_date ?? '')
        const siteName = String(prov.site_name ?? '')
        const siteAddr = String(prov.site_address ?? '')
        const hasAny = orgName || auditorName || auditType || certNo || scope || nextDate
        if (!job || !hasAny) return null
        return (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-primary" />
                Audit Report Summary
              </CardTitle>
              <CardDescription>
                Key metadata extracted from the audit document by AI analysis.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {orgName ? (
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Organisation audited
                  </p>
                  <p className="mt-1 font-medium text-foreground">{orgName}</p>
                </div>
              ) : null}
              {siteName ? (
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Site / Facility</p>
                  <p className="mt-1 font-medium text-foreground">{siteName}</p>
                  {siteAddr ? <p className="mt-1 text-xs text-muted-foreground">{siteAddr}</p> : null}
                </div>
              ) : null}
              {auditorName ? (
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-1">
                    <User size={12} /> Lead auditor
                  </p>
                  <p className="mt-1 font-medium text-foreground">{auditorName}</p>
                </div>
              ) : null}
              {auditType ? (
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Audit type</p>
                  <p className="mt-1 font-medium text-foreground capitalize">
                    {auditType.replace(/_/g, ' ')}
                  </p>
                </div>
              ) : null}
              {certNo ? (
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Certificate / Registration No.
                  </p>
                  <p className="mt-1 font-medium text-foreground">{certNo}</p>
                </div>
              ) : null}
              {scope ? (
                <div className="col-span-full rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Audit scope</p>
                  <p className="mt-1 text-sm text-foreground line-clamp-4">{scope}</p>
                </div>
              ) : null}
              {nextDate ? (
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Next audit date
                  </p>
                  <p className="mt-1 font-medium text-foreground">{formatDate(nextDate)}</p>
                </div>
              ) : null}
            </CardContent>
          </Card>
        )
      })()}

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
        <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>Evidence and mappings</CardTitle>
              <CardDescription>
                ISO evidence candidates and scheme mappings extracted from the source document.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {job.evidence_preview_json?.length ? (
                  job.evidence_preview_json.slice(0, 8).map((mapping, index) => (
                    <Badge key={`evidence-${index}`} variant="secondary">
                      {String(mapping.clause_number || mapping.clause_id || 'Clause')}{' '}
                      {String(mapping.standard || '')}
                    </Badge>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No clause-level evidence preview available yet.
                  </p>
                )}
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Positive evidence
                  </p>
                  <p className="mt-1 font-medium text-foreground">
                    {job.positive_summary_json?.length || 0}
                  </p>
                </div>
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Non-compliances
                  </p>
                  <p className="mt-1 font-medium text-foreground">
                    {job.nonconformity_summary_json?.length || 0}
                  </p>
                </div>
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Improvements
                  </p>
                  <p className="mt-1 font-medium text-foreground">
                    {job.improvement_summary_json?.length || 0}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Promotion impact</CardTitle>
              <CardDescription>
                What the accepted drafts will write into the live governance system.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Accepted findings
                  </p>
                  <p className="mt-1 font-medium text-foreground">{approvedCount}</p>
                </div>
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    ISO evidence links
                  </p>
                  <p className="mt-1 font-medium text-foreground">{acceptedClauseCount}</p>
                </div>
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Action candidates
                  </p>
                  <p className="mt-1 font-medium text-foreground">{acceptedActionCandidates}</p>
                </div>
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Risk candidates
                  </p>
                  <p className="mt-1 font-medium text-foreground">{acceptedRiskCandidates}</p>
                </div>
              </div>
              {schemeAlignment ? (
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Scheme alignment
                  </p>
                  <p className="mt-1 font-medium text-foreground">
                    {String(schemeAlignment.status || 'pending').replace(/_/g, ' ')}
                  </p>
                  {schemeAlignment.reason ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {String(schemeAlignment.reason)}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
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

