import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, FileText, Loader2, ShieldCheck } from 'lucide-react'
import {
  externalAuditImportsApi,
  type ExternalAuditImportDraft,
  type ExternalAuditImportJob,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'

export default function AuditImportReview() {
  const { auditId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const jobId = Number(searchParams.get('jobId') || '')

  const [job, setJob] = useState<ExternalAuditImportJob | null>(null)
  const [drafts, setDrafts] = useState<ExternalAuditImportDraft[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyDraftId, setBusyDraftId] = useState<number | null>(null)
  const [isPromoting, setIsPromoting] = useState(false)

  const load = useCallback(async () => {
    if (!jobId) {
      setError('Missing import job reference.')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const [jobRes, draftsRes] = await Promise.all([
        externalAuditImportsApi.getJob(jobId),
        externalAuditImportsApi.listDrafts(jobId),
      ])
      setJob(jobRes.data)
      setDrafts(draftsRes.data)
    } catch (err) {
      console.error('Failed to load external audit review workspace', err)
      setError('Failed to load the import review workspace. Please retry.')
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    void load()
  }, [load])

  const acceptedCount = useMemo(
    () => drafts.filter((draft) => draft.status === 'accepted' || draft.status === 'promoted').length,
    [drafts],
  )

  const handleDraftDecision = async (draftId: number, status: 'accepted' | 'rejected') => {
    setBusyDraftId(draftId)
    try {
      const res = await externalAuditImportsApi.reviewDraft(draftId, { status })
      setDrafts((prev) => prev.map((draft) => (draft.id === draftId ? res.data : draft)))
    } catch (err) {
      console.error('Failed to update draft review decision', err)
      setError('Failed to update the draft. Please retry.')
    } finally {
      setBusyDraftId(null)
    }
  }

  const handlePromote = async () => {
    if (!job) return
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
            OCR and analysis stay in draft until you explicitly approve promotion into live findings.
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => navigate(`/audits/${auditId}/execute`)}>
            <FileText size={16} />
            Open Audit Run
          </Button>
          <Button onClick={handlePromote} disabled={acceptedCount === 0 || isPromoting}>
            {isPromoting ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
            Promote Accepted Drafts
          </Button>
        </div>
      </div>

      {error ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex items-center gap-3 p-5">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      ) : null}

      {job ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-primary" />
              {job.reference_number}
            </CardTitle>
            <CardDescription>
              Status: {job.status.replace(/_/g, ' ')}. {job.analysis_summary || 'Analysis summary pending.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Source file</p>
              <p className="mt-1 font-medium text-foreground">{job.source_filename || 'Source document'}</p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Extraction</p>
              <p className="mt-1 font-medium text-foreground">{job.extraction_method || 'pending'}</p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Accepted drafts</p>
              <p className="mt-1 font-medium text-foreground">{acceptedCount}</p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4">
        {drafts.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              No draft findings were produced yet. If processing has just started, refresh shortly.
            </CardContent>
          </Card>
        ) : (
          drafts.map((draft) => (
            <Card key={draft.id}>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle className="text-xl">{draft.title}</CardTitle>
                  <Badge variant={draft.severity === 'high' ? 'high' : draft.severity === 'low' ? 'low' : 'medium'}>
                    {draft.severity}
                  </Badge>
                  <Badge variant="outline">{draft.status.replace(/_/g, ' ')}</Badge>
                  {draft.confidence_score != null ? (
                    <Badge variant="secondary">{Math.round(draft.confidence_score * 100)}% confidence</Badge>
                  ) : null}
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
                      {String(mapping.standard || 'ISO')}
                    </Badge>
                  ))}
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button
                    variant="success"
                    onClick={() => void handleDraftDecision(draft.id, 'accepted')}
                    disabled={busyDraftId === draft.id || draft.status === 'promoted'}
                  >
                    {busyDraftId === draft.id ? <Loader2 size={16} className="animate-spin" /> : null}
                    Accept
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => void handleDraftDecision(draft.id, 'rejected')}
                    disabled={busyDraftId === draft.id || draft.status === 'promoted'}
                  >
                    Reject
                  </Button>
                  {draft.promoted_finding_id ? (
                    <Link
                      to={`/audits/${draft.audit_run_id}/execute`}
                      className="inline-flex items-center text-sm font-medium text-primary hover:underline"
                    >
                      View live finding
                    </Link>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
