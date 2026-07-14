import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, Loader2, Sparkles, CheckCircle2, XCircle } from 'lucide-react'
import {
  getApiErrorMessage,
  knowledgeBankApi,
  type KnowledgeEvidenceLink,
  type RelatedDocumentHit,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { knowledgeExceptionsClosedLoopHref } from '../helpers/knowledgeExceptionsLinks'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card'
import { EmptyState } from './ui/EmptyState'

const signalBadge = (signal?: string | null) => {
  const value = (signal || 'nonconformity').toLowerCase()
  if (value === 'evidence') return <Badge variant="success">Evidence</Badge>
  if (value === 'opportunity') return <Badge variant="submitted">Opportunity</Badge>
  if (value === 'gap') return <Badge variant="warning">Gap</Badge>
  return <Badge variant="destructive">Nonconformity</Badge>
}

const statusBadge = (link: KnowledgeEvidenceLink) => {
  if (link.status === 'confirmed') return <Badge variant="success">Confirmed</Badge>
  if (link.status === 'proposed') return <Badge variant="submitted">Proposed</Badge>
  if (link.status === 'needs_review') return <Badge variant="warning">Needs review</Badge>
  if (link.status === 'rejected') return <Badge variant="destructive">Rejected</Badge>
  return <Badge variant="secondary">{link.status}</Badge>
}

export interface StandardsAssessmentPanelProps {
  entityType: 'incident' | 'complaint' | 'near_miss' | 'rta' | 'audit_finding'
  entityId: number | string
  title?: string
}

export function StandardsAssessmentPanel({
  entityType,
  entityId,
  title = 'Standards Assessment',
}: StandardsAssessmentPanelProps) {
  const [links, setLinks] = useState<KnowledgeEvidenceLink[]>([])
  const [related, setRelated] = useState<RelatedDocumentHit[]>([])
  const [statement, setStatement] = useState<string | null>(null)
  const [signalType, setSignalType] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [assessing, setAssessing] = useState(false)

  const exceptionsHref = useMemo(
    () => knowledgeExceptionsClosedLoopHref(entityType, entityId),
    [entityType, entityId],
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await knowledgeBankApi.listEntityAssessment(entityType, entityId)
      setLinks(response.data)
      if (response.data[0]?.signal_type) {
        setSignalType(response.data[0].signal_type)
      }
      if (response.data[0]?.notes) {
        setStatement(response.data[0].notes)
      }
    } catch (err) {
      // Missing assessment is an empty state, not a user-facing failure.
      // Axios 404 / route drift should not toast "Request failed with status code 404".
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        setLinks([])
      } else {
        toast.error(
          getApiErrorMessage(err, 'Could not load standards assessment. Please try again.'),
        )
      }
    } finally {
      setLoading(false)
    }
  }, [entityType, entityId])

  useEffect(() => {
    void load()
  }, [load])

  const runAssess = async () => {
    setAssessing(true)
    try {
      const response = await knowledgeBankApi.assessEntity(entityType, entityId)
      setLinks(response.data.links)
      setRelated(response.data.related_documents)
      setStatement(response.data.assessment_statement)
      setSignalType(response.data.signal_type)
      toast.success(
        `Assessed against standards — ${response.data.links_created} proposed link(s) sent to Exceptions`,
      )
    } catch (err) {
      toast.error(
        getApiErrorMessage(err, 'Could not assess against standards. Please try again.'),
      )
    } finally {
      setAssessing(false)
    }
  }

  const confirmLink = async (linkId: number) => {
    try {
      await knowledgeBankApi.confirmLink(linkId)
      toast.success('Link confirmed')
      await load()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    }
  }

  const rejectLink = async (linkId: number) => {
    try {
      await knowledgeBankApi.rejectLink(linkId)
      toast.success('Link rejected')
      await load()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-primary" />
            {title}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            AI maps this record to ISO clauses as a governed signal — never silent auto-confirm for
            operational cases.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 shrink-0">
          <Button type="button" variant="outline" asChild>
            <Link
              to={exceptionsHref}
              data-testid="standards-exceptions-deeplink"
              title="Review proposed links filtered to this case"
            >
              <ExternalLink className="h-4 w-4" />
              Review in Exceptions
            </Link>
          </Button>
          <Button type="button" onClick={() => void runAssess()} disabled={assessing}>
            {assessing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Assess against standards
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground" data-testid="standards-exceptions-hint">
          Proposed signals also appear in{' '}
          <Link
            className="text-primary underline-offset-2 hover:underline"
            to={exceptionsHref}
          >
            Knowledge Exceptions
          </Link>{' '}
          (pre-filtered to this {entityType.replace('_', ' ')}). Confirm or reject there to return
          to this case.
        </p>

        {(signalType || statement) && (
          <div className="rounded-md border border-border/60 bg-muted/30 p-3 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              Signal type {signalBadge(signalType)}
            </div>
            {statement ? (
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">{statement}</p>
            ) : null}
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading assessment…
          </div>
        ) : links.length === 0 ? (
          <EmptyState
            title="No standards assessment yet"
            description="Run Assess against standards to propose clause links for human review."
          />
        ) : (
          <ul className="space-y-3">
            {links.map((link) => (
              <li
                key={link.id}
                className="rounded-md border border-border/60 p-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-sm">{link.clause_id}</span>
                    {statusBadge(link)}
                    {signalBadge(link.signal_type)}
                    {link.scheme ? <Badge variant="secondary">{link.scheme}</Badge> : null}
                  </div>
                  {link.title ? <p className="text-sm">{link.title}</p> : null}
                  {link.rationale ? (
                    <p className="text-xs text-muted-foreground">{link.rationale}</p>
                  ) : null}
                </div>
                {(link.status === 'proposed' || link.status === 'needs_review') && (
                  <div className="flex gap-2 shrink-0">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void confirmLink(link.id)}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" /> Confirm
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => void rejectLink(link.id)}
                    >
                      <XCircle className="h-3.5 w-3.5" /> Reject
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {related.length > 0 ? (
          <div className="space-y-2">
            <p className="text-sm font-medium">Related knowledge-bank documents</p>
            <ul className="space-y-1">
              {related.map((doc) => (
                <li key={doc.document_id} className="text-sm">
                  <Link
                    className="text-primary underline-offset-2 hover:underline"
                    to={`/documents/${doc.document_id}?tab=evidence`}
                    title="Open Standards & Evidence tab"
                  >
                    {doc.title || `Document ${doc.document_id}`}
                  </Link>
                  <span className="text-muted-foreground"> · score {Math.round(doc.score)}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
