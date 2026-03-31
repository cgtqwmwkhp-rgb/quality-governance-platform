import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  Info,
  Loader2,
  ShieldCheck,
  User,
} from 'lucide-react'
import {
  auditsApi,
  externalAuditImportsApi,
  type AuditRunDetail,
  type ExternalAuditImportDraft,
  type ExternalAuditImportJob,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'

function getSeverityVariant(severity: string) {
  if (severity === 'critical') return 'critical'
  if (severity === 'high') return 'high'
  if (severity === 'low') return 'low'
  return 'medium'
}

function getConfidenceTier(confidence: number | null | undefined): {
  label: string
  color: string
  bgColor: string
  borderColor: string
} {
  if (confidence == null)
    return {
      label: 'Unknown',
      color: 'text-slate-500',
      bgColor: 'bg-slate-50',
      borderColor: 'border-slate-200',
    }
  const pct = Math.round(confidence * 100)
  if (pct >= 85)
    return {
      label: `${pct}%`,
      color: 'text-emerald-700',
      bgColor: 'bg-emerald-50',
      borderColor: 'border-emerald-200',
    }
  if (pct >= 60)
    return {
      label: `${pct}%`,
      color: 'text-amber-700',
      bgColor: 'bg-amber-50',
      borderColor: 'border-amber-200',
    }
  return {
    label: `${pct}%`,
    color: 'text-red-700',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
  }
}

function getAnalysisMethodLabel(provenance: Record<string, unknown> | null | undefined): string {
  if (!provenance) return 'rule-based'
  const method = String(provenance.analysis_method || '')
  if (method.includes('consensus') || method.includes('ai_structured')) return 'AI consensus'
  if (method.includes('mistral')) return 'Mistral AI'
  if (method.includes('gemini')) return 'Gemini AI'
  if (method.includes('rule_based')) return 'Rule-based'
  if (method.includes('normalized')) return 'Rule-based'
  return method || 'rule-based'
}

const SEVERITY_WEIGHT: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
}

function reviewUrgency(draft: ExternalAuditImportDraft): number {
  const confidenceInverse = 1 - (draft.confidence_score ?? 0.5)
  const severityScore = SEVERITY_WEIGHT[draft.severity] ?? 2
  return confidenceInverse * 10 + severityScore
}

function humanizeLabel(value: string | null | undefined) {
  if (!value) return ''
  return value.replace(/_/g, ' ')
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
  return { path: '/compliance', label: 'Open Compliance Summary' }
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
  const [loading, setLoading] = useState(true)
  const initialLoadDone = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [queueNotice, setQueueNotice] = useState<string | null>(
    searchParams.get('queueError') === '1'
      ? 'The import workspace is ready, but automatic processing did not start. Retry queueing below.'
      : null,
  )
  const [busyDraftId, setBusyDraftId] = useState<number | null>(null)
  const [isPromoting, setIsPromoting] = useState(false)
  const [isQueueing, setIsQueueing] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const processingTriggered = useRef(false)

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

      const [jobRes, draftsRes] = await Promise.all([
        Promise.resolve(resolvedJobRes),
        externalAuditImportsApi.listDrafts(resolvedJobRes.data.id),
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
    } catch (err) {
      console.error('Failed to load external audit review workspace', err)
      setAuditRun(null)
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404 && !jobId) {
        setError(
          'No import job has been created for this audit yet. Attach a source report and queue the import first.',
        )
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
    if (!job || !['processing', 'promoting'].includes(job.status)) return
    const timeoutId = window.setTimeout(() => {
      void load()
    }, 5000)
    return () => window.clearTimeout(timeoutId)
  }, [job, load])

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
  const promotedCount = useMemo(
    () => drafts.filter((draft) => draft.status === 'promoted' || draft.promoted_finding_id).length,
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
      acceptedDrafts.filter((draft) =>
        ['nonconformity', 'competence_gap', 'finding'].includes(draft.finding_type),
      ).length,
    [acceptedDrafts],
  )
  const acceptedRiskCandidates = useMemo(
    () =>
      acceptedDrafts.filter(
        (draft) =>
          ['nonconformity', 'competence_gap', 'finding'].includes(draft.finding_type) &&
          ['high', 'critical'].includes(draft.severity),
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

  const handleDraftDecision = async (draftId: number, status: 'accepted' | 'rejected') => {
    setBusyDraftId(draftId)
    setError(null)
    try {
      const res = await externalAuditImportsApi.reviewDraft(draftId, { status })
      setDrafts((prev) => prev.map((draft) => (draft.id === draftId ? res.data : draft)))
      setError(null)
    } catch (err) {
      console.error('Failed to update draft review decision', err)
      setError('Failed to update the draft. Please retry.')
    } finally {
      setBusyDraftId(null)
    }
  }

  const handlePromote = async () => {
    if (!job || promoteableCount === 0 || ['completed', 'promoting'].includes(job.status)) return
    setIsPromoting(true)
    setError(null)
    try {
      await externalAuditImportsApi.promoteJob(job.id)
      await load()
    } catch (err) {
      console.error('Failed to promote imported audit findings', err)
      setError('Promotion failed. Review the accepted drafts and try again.')
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
          <p className="mt-1 text-muted-foreground">
            OCR and analysis stay in draft until you approve promotion into completed governance
            outcomes.
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => navigate(specialistHome.path)} disabled={!job}>
            <FileText size={16} />
            {specialistHome.label}
          </Button>
          <Button
            onClick={handlePromote}
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

      {error ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex items-center justify-between gap-3 p-5">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-destructive" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => void load()}>
              Retry
            </Button>
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
                  {resolvedTemplateName ||
                    (resolvedTemplateId ? `Template ${resolvedTemplateId}` : 'Pending resolution')}
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
                  Accepted drafts
                </p>
                <p className="mt-1 font-medium text-foreground">{approvedCount}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {promoteableCount} awaiting promotion, {promotedCount} promoted
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
                  <p className="mt-1 font-medium text-foreground">
                    {job.score_percentage != null
                      ? `${job.score_percentage.toFixed(1)}%`
                      : 'No explicit score extracted'}
                  </p>
                  {job.overall_score != null && job.max_score != null ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {job.overall_score} / {job.max_score}
                    </p>
                  ) : null}
                </div>
                <div className="rounded-lg border border-border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Issuer</p>
                  <p className="mt-1 font-medium text-foreground">
                    {job.issuer_name || 'Reviewer confirmation required'}
                  </p>
                  {job.report_date ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Report date: {new Date(job.report_date).toLocaleDateString()}
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
                    {job.score_breakdown_json.slice(0, 6).map((item, index) => (
                      <div
                        key={`score-breakdown-${index}`}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="text-foreground">
                          {String(item.label || `Section ${index + 1}`)}
                        </span>
                        <span className="text-muted-foreground">
                          {String(item.score ?? '-')} / {String(item.max_score ?? '-')} (
                          {String(item.percentage ?? '-')}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {job &&
      (job.organization_name ||
        job.auditor_name ||
        job.audit_type ||
        job.certificate_number ||
        job.audit_scope ||
        job.next_audit_date) ? (
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
            {job.organization_name ? (
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Organisation audited
                </p>
                <p className="mt-1 font-medium text-foreground">{job.organization_name}</p>
              </div>
            ) : null}
            {job.auditor_name ? (
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-1">
                  <User size={12} /> Lead auditor
                </p>
                <p className="mt-1 font-medium text-foreground">{job.auditor_name}</p>
              </div>
            ) : null}
            {job.audit_type ? (
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Audit type</p>
                <p className="mt-1 font-medium text-foreground capitalize">
                  {job.audit_type.replace(/_/g, ' ')}
                </p>
              </div>
            ) : null}
            {job.certificate_number ? (
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Certificate / Registration No.
                </p>
                <p className="mt-1 font-medium text-foreground">{job.certificate_number}</p>
              </div>
            ) : null}
            {job.audit_scope ? (
              <div className="col-span-full rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Audit scope</p>
                <p className="mt-1 text-sm text-foreground">{job.audit_scope}</p>
              </div>
            ) : null}
            {job.next_audit_date ? (
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Next audit date
                </p>
                <p className="mt-1 font-medium text-foreground">
                  {new Date(job.next_audit_date).toLocaleDateString()}
                </p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {isProcessing ? (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="flex items-center gap-4 p-6">
            <Loader2 size={24} className="animate-spin text-primary" />
            <div>
              <p className="font-medium text-foreground">
                Processing import&hellip;
              </p>
              <p className="text-sm text-muted-foreground">
                Extracting text, running analysis, and generating draft findings. This may take up to
                two minutes.
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
            <CardDescription>These items should be checked before promotion.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {job.processing_warnings_json.map((warning, index) => (
              <p key={`warning-${index}`} className="text-sm text-foreground">
                {warning}
              </p>
            ))}
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
        specialistHome={specialistHome}
        onDecision={handleDraftDecision}
        onLoad={load}
      />
    </div>
  )
}

function DraftFindingsList({
  drafts,
  job,
  error,
  busyDraftId,
  specialistHome,
  onDecision,
  onLoad,
}: {
  drafts: ExternalAuditImportDraft[]
  job: ExternalAuditImportJob | null
  error: string | null
  busyDraftId: number | null
  specialistHome: { path: string; label: string }
  onDecision: (id: number, status: 'accepted' | 'rejected') => void
  onLoad: () => void
}) {
  const [expandedProvenance, setExpandedProvenance] = useState<Set<number>>(new Set())

  const sortedDrafts = useMemo(() => {
    return [...drafts].sort((a, b) => reviewUrgency(b) - reviewUrgency(a))
  }, [drafts])

  const toggleProvenance = (id: number) => {
    setExpandedProvenance((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (drafts.length === 0) {
    return (
      <div className="grid gap-4">
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            {job?.status === 'processing' || job?.status === 'promoting'
              ? 'Processing is still running. This workspace refreshes automatically while analysis is in progress.'
              : job?.status === 'queued'
                ? 'Waiting for processing to start. Click Retry Queue above if this persists.'
                : error
                  ? 'The latest import state could not be refreshed. Retry to continue reviewing this workspace.'
                  : 'No draft findings were produced for this import. Review the source document and processing warnings before promoting.'}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {drafts.length} finding(s) sorted by review urgency (low confidence + high severity first)
        </p>
        <Button variant="outline" size="sm" onClick={onLoad}>
          Refresh
        </Button>
      </div>
      {sortedDrafts.map((draft) => {
        const tier = getConfidenceTier(draft.confidence_score)
        const methodLabel = getAnalysisMethodLabel(draft.provenance_json ?? null)
        const isExpanded = expandedProvenance.has(draft.id)

        return (
          <Card key={draft.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-xl">{draft.title}</CardTitle>
                <Badge variant={getSeverityVariant(draft.severity)}>{draft.severity}</Badge>
                <Badge variant="outline">{draft.status.replace(/_/g, ' ')}</Badge>
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${tier.color} ${tier.bgColor} ${tier.borderColor}`}
                >
                  {tier.label} confidence
                </span>
                <Badge variant="secondary">{methodLabel}</Badge>
              </div>
              <CardDescription>{draft.finding_type.replace(/_/g, ' ')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-foreground">{draft.description}</p>

              {draft.evidence_snippets_json?.length ? (
                <div className="rounded-lg bg-surface p-4 text-sm text-muted-foreground">
                  {draft.evidence_snippets_json[0]}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-2">
                {draft.mapped_frameworks_json?.map((mapping, index) => (
                  <Badge key={`framework-${draft.id}-${index}`} variant="info">
                    {String(mapping.framework || 'Framework')}
                  </Badge>
                ))}
                {draft.mapped_standards_json?.map((mapping, index) => (
                  <Badge key={`standard-${draft.id}-${index}`} variant="secondary">
                    {String(mapping.clause_number || mapping.standard || 'ISO')}
                  </Badge>
                ))}
              </div>

              {(draft.suggested_action_title || draft.suggested_risk_title) && (
                <div className="grid gap-3 md:grid-cols-2">
                  {draft.suggested_action_title ? (
                    <div className="rounded-lg border border-border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Proposed action
                      </p>
                      <p className="mt-1 text-sm text-foreground">
                        {draft.suggested_action_title}
                      </p>
                    </div>
                  ) : null}
                  {draft.suggested_risk_title ? (
                    <div className="rounded-lg border border-border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Proposed risk
                      </p>
                      <p className="mt-1 text-sm text-foreground">{draft.suggested_risk_title}</p>
                    </div>
                  ) : null}
                </div>
              )}

              {draft.provenance_json ? (
                <div className="rounded-lg border border-border">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between p-3 text-left text-xs text-muted-foreground hover:bg-surface"
                    onClick={() => toggleProvenance(draft.id)}
                  >
                    <span className="flex items-center gap-1">
                      <Info size={12} />
                      Provenance &amp; confidence detail
                    </span>
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  {isExpanded ? (
                    <ProvenanceDetail provenance={draft.provenance_json} />
                  ) : null}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <Button
                  variant="success"
                  onClick={() => void onDecision(draft.id, 'accepted')}
                  disabled={busyDraftId === draft.id || draft.status === 'promoted'}
                >
                  {busyDraftId === draft.id ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : null}
                  Accept
                </Button>
                <Button
                  variant="outline"
                  onClick={() => void onDecision(draft.id, 'rejected')}
                  disabled={busyDraftId === draft.id || draft.status === 'promoted'}
                >
                  Reject
                </Button>
                {draft.promoted_finding_id ? (
                  <Link
                    to={specialistHome.path}
                    className="inline-flex items-center text-sm font-medium text-primary hover:underline"
                  >
                    {specialistHome.label}
                  </Link>
                ) : null}
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

function ProvenanceDetail({ provenance }: { provenance: Record<string, unknown> }) {
  const pageNumber = provenance.page_number != null ? String(provenance.page_number) : null
  const analysisMethod = String(provenance.analysis_method || 'unknown')
  const trigger = provenance.trigger ? String(provenance.trigger) : null
  const aiConfidence = provenance.ai_confidence != null ? String(provenance.ai_confidence) : null
  const aiProvider = provenance.ai_provider ? String(provenance.ai_provider) : null
  const clauseRef = provenance.clause_reference ? String(provenance.clause_reference) : null
  const cadDeadline = provenance.corrective_action_deadline
    ? String(provenance.corrective_action_deadline)
    : null
  const consensus = provenance._consensus ? String(provenance._consensus) : null
  const providers = Array.isArray(provenance._providers)
    ? (provenance._providers as string[]).join(', ')
    : null

  return (
    <div className="border-t border-border p-3 text-xs text-muted-foreground space-y-1">
      {pageNumber && <p>Source page: {pageNumber}</p>}
      <p>Analysis method: {analysisMethod}</p>
      {trigger && (
        <p>
          Trigger phrase: &quot;{trigger}&quot;
        </p>
      )}
      {aiConfidence && <p>AI raw confidence: {aiConfidence}</p>}
      {aiProvider && <p>AI provider: {aiProvider}</p>}
      {clauseRef && <p>Clause reference: {clauseRef}</p>}
      {cadDeadline && <p>Corrective action deadline: {cadDeadline}</p>}
      {consensus && (
        <p>
          Consensus:{' '}
          <span
            className={
              consensus === 'agreed'
                ? 'font-semibold text-emerald-600'
                : 'font-semibold text-amber-600'
            }
          >
            {consensus === 'agreed' ? 'Confirmed by multiple providers' : 'Single source'}
          </span>
        </p>
      )}
      {providers && <p>Providers: {providers}</p>}
    </div>
  )
}
