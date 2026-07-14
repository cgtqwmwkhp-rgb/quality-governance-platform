import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2, XCircle } from 'lucide-react'
import {
  getApiErrorMessage,
  knowledgeBankApi,
  type KnowledgeEvidenceLink,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { cn } from '../helpers/utils'
import {
  exceptionEntityHref,
  isSafeReturnTo,
  parseEntityTypeFilter,
  type ExceptionsEntityTypeFilter,
} from '../helpers/knowledgeExceptionsLinks'

export {
  exceptionEntityHref,
  isSafeReturnTo,
  knowledgeExceptionsClosedLoopHref,
  parseEntityTypeFilter,
} from '../helpers/knowledgeExceptionsLinks'

const reportFailure = (err: unknown): string => {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

const statusBadge = (status: string) => {
  if (status === 'proposed') return <Badge variant="submitted">Proposed</Badge>
  if (status === 'needs_review') return <Badge variant="warning">Needs review</Badge>
  return <Badge variant="outline">{status}</Badge>
}

const signalBadge = (signal?: string | null) => {
  const value = (signal || '').toLowerCase()
  if (value === 'evidence') return <Badge variant="success">Evidence</Badge>
  if (value === 'opportunity') return <Badge variant="submitted">Opportunity</Badge>
  if (value === 'gap') return <Badge variant="warning">Gap</Badge>
  if (value === 'nonconformity') return <Badge variant="destructive">Nonconformity</Badge>
  if (!value) return null
  return <Badge variant="outline">{signal}</Badge>
}

/** Known source entity types for the Assessor + document evidence inbox. */
const ENTITY_TYPE_OPTIONS = [
  { value: 'all', label: 'All entity types' },
  { value: 'document', label: 'Document' },
  { value: 'incident', label: 'Incident' },
  { value: 'complaint', label: 'Complaint' },
  { value: 'near_miss', label: 'Near miss' },
  { value: 'rta', label: 'RTA' },
  { value: 'audit_finding', label: 'Audit finding' },
] as const

/** Signal types — filtered server-side via GET /exceptions?signal_type=. */
const SIGNAL_TYPE_OPTIONS = [
  { value: 'all', label: 'All signal types' },
  { value: 'evidence', label: 'Evidence' },
  { value: 'nonconformity', label: 'Nonconformity' },
  { value: 'gap', label: 'Gap' },
  { value: 'opportunity', label: 'Opportunity' },
] as const

type SignalTypeFilter = (typeof SIGNAL_TYPE_OPTIONS)[number]['value']

const ENTITY_LABELS: Record<string, string> = {
  document: 'Document',
  incident: 'Incident',
  complaint: 'Complaint',
  near_miss: 'Near miss',
  rta: 'RTA',
  audit_finding: 'Audit finding',
}

export default function KnowledgeExceptions() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [items, setItems] = useState<KnowledgeEvidenceLink[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [acting, setActing] = useState(false)
  const [entityTypeFilter, setEntityTypeFilter] = useState<ExceptionsEntityTypeFilter>(() =>
    parseEntityTypeFilter(searchParams.get('entity_type')),
  )
  const [signalTypeFilter, setSignalTypeFilter] = useState<SignalTypeFilter>('all')

  const returnTo = useMemo(() => {
    const raw = searchParams.get('returnTo')
    return isSafeReturnTo(raw) ? raw : null
  }, [searchParams])

  // Hydrate entity_type from deep link / shareable URL.
  useEffect(() => {
    const fromUrl = parseEntityTypeFilter(searchParams.get('entity_type'))
    setEntityTypeFilter((prev) => (prev === fromUrl ? prev : fromUrl))
  }, [searchParams])

  // Keep entity_type in the URL so refresh / share preserves the filter.
  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (entityTypeFilter === 'all') next.delete('entity_type')
    else next.set('entity_type', entityTypeFilter)
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [entityTypeFilter, searchParams, setSearchParams])

  const loadExceptions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await knowledgeBankApi.listExceptions({
        entityType: entityTypeFilter === 'all' ? undefined : entityTypeFilter,
        signalType: signalTypeFilter === 'all' ? undefined : signalTypeFilter,
      })
      setItems(response.data)
      setSelectedIds([])
    } catch (err) {
      setError(reportFailure(err))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [entityTypeFilter, signalTypeFilter])

  useEffect(() => {
    void loadExceptions()
  }, [loadExceptions])

  /** Server already filters signal_type; inbox page still capped at 200. */
  const visibleItems = items

  const allSelected = useMemo(
    () => visibleItems.length > 0 && selectedIds.length === visibleItems.length,
    [visibleItems, selectedIds.length],
  )

  const returnToCase = useCallback(() => {
    if (returnTo) {
      navigate(returnTo)
    }
  }, [navigate, returnTo])

  const toggleAll = () => {
    setSelectedIds(allSelected ? [] : visibleItems.map((i) => i.id))
  }

  const toggleOne = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  const handleConfirmOne = async (id: number) => {
    setActing(true)
    try {
      await knowledgeBankApi.confirmLink(id)
      toast.success('Link confirmed')
      if (returnTo) {
        returnToCase()
        return
      }
      await loadExceptions()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActing(false)
    }
  }

  const handleRejectOne = async (id: number) => {
    setActing(true)
    try {
      await knowledgeBankApi.rejectLink(id)
      toast.success('Link rejected')
      if (returnTo) {
        returnToCase()
        return
      }
      await loadExceptions()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActing(false)
    }
  }

  const handleBulkConfirm = async () => {
    if (selectedIds.length === 0) return
    setActing(true)
    try {
      const response = await knowledgeBankApi.bulkConfirm(selectedIds)
      toast.success(`Confirmed ${response.data.count} item(s)`)
      setSelectedIds([])
      if (returnTo) {
        returnToCase()
        return
      }
      await loadExceptions()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActing(false)
    }
  }

  const handleBulkReject = async () => {
    if (selectedIds.length === 0) return
    const rationale = window.prompt(
      'Reject rationale (required — recorded on each link for auditability):',
    )
    if (!rationale || rationale.trim().length < 3) {
      toast.error('Reject requires a rationale (min 3 characters)')
      return
    }
    setActing(true)
    try {
      await Promise.all(
        selectedIds.map((id) => knowledgeBankApi.rejectLink(id, rationale.trim())),
      )
      toast.success(`Rejected ${selectedIds.length} item(s)`)
      setSelectedIds([])
      if (returnTo) {
        returnToCase()
        return
      }
      await loadExceptions()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActing(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Knowledge Exceptions</h1>
          <p className="text-muted-foreground mt-1">
            AI evidence and operational standards signals requiring operator review
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            disabled={selectedIds.length === 0 || acting}
            onClick={() => void handleBulkConfirm()}
          >
            <CheckCircle2 className="w-4 h-4 mr-2" />
            Bulk confirm ({selectedIds.length})
          </Button>
          <Button
            variant="outline"
            disabled={selectedIds.length === 0 || acting}
            onClick={() => void handleBulkReject()}
          >
            <XCircle className="w-4 h-4 mr-2" />
            Bulk reject
          </Button>
        </div>
      </div>

      <Card className="p-4 border-primary/20 bg-primary/5" data-testid="exceptions-map-cta-banner">
        <p className="text-sm font-medium text-foreground">Map inputs → standards</p>
        <p className="text-xs text-muted-foreground mt-1">
          Open a document&apos;s Standards &amp; Evidence tab or a case detail Standards Assessment
          panel, then run <strong>Map to ISO / UVDB / Planet Mark</strong>. Proposed links land here
          for confirm/reject (reject requires a rationale).
        </p>
      </Card>

      {returnTo ? (
        <Card
          className="p-4 border-primary/20 bg-primary/5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
          data-testid="exceptions-return-to-case"
        >
          <div>
            <p className="text-sm font-medium text-foreground">Reviewing from a case Standards tab</p>
            <p className="text-xs text-muted-foreground mt-1">
              Confirm or reject a signal to return to the case, or go back now.
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" asChild>
            <Link to={returnTo} data-testid="exceptions-return-to-case-link">
              <ArrowLeft className="w-4 h-4" />
              Back to case
            </Link>
          </Button>
        </Card>
      ) : null}

      <div className="flex flex-col sm:flex-row sm:items-end gap-3">
        <div className="space-y-1.5 min-w-[12rem]">
          <label htmlFor="exceptions-entity-type" className="text-xs font-medium text-muted-foreground">
            Entity type
          </label>
          <Select
            value={entityTypeFilter}
            onValueChange={(value) => setEntityTypeFilter(value as ExceptionsEntityTypeFilter)}
          >
            <SelectTrigger id="exceptions-entity-type" aria-label="Filter by entity type">
              <SelectValue placeholder="All entity types" />
            </SelectTrigger>
            <SelectContent>
              {ENTITY_TYPE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5 min-w-[12rem]">
          <label htmlFor="exceptions-signal-type" className="text-xs font-medium text-muted-foreground">
            Signal type
          </label>
          <Select
            value={signalTypeFilter}
            onValueChange={(value) => {
              setSignalTypeFilter(value as SignalTypeFilter)
              setSelectedIds([])
            }}
          >
            <SelectTrigger id="exceptions-signal-type" aria-label="Filter by signal type">
              <SelectValue placeholder="All signal types" />
            </SelectTrigger>
            <SelectContent>
              {SIGNAL_TYPE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <p className="text-xs text-muted-foreground sm:pb-2" data-testid="exceptions-filter-honesty">
          Showing {visibleItems.length}
          {entityTypeFilter !== 'all' ? ` · entity=${entityTypeFilter}` : ''}
          {signalTypeFilter !== 'all' ? ` · signal=${signalTypeFilter}` : ''}
          {' '}(server filters; inbox page ≤200 — not a global facet total)
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {error ? null : visibleItems.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 className="w-8 h-8 text-success" />}
          title={
            entityTypeFilter !== 'all' || signalTypeFilter !== 'all'
              ? 'No matches for filters'
              : 'Inbox clear'
          }
          description={
            entityTypeFilter !== 'all' || signalTypeFilter !== 'all'
              ? 'Server returned no exceptions for these filters on the current inbox page (≤200). This is not a global zero.'
              : 'No proposed or needs-review evidence links at this time.'
          }
        />
      ) : (
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-sm text-muted-foreground px-1">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="rounded border-border"
            />
            Select all visible
          </label>
          {visibleItems.map((item) => {
            const href = exceptionEntityHref(item.entity_type, item.entity_id)
            const entityLabel = ENTITY_LABELS[item.entity_type] ?? item.entity_type
            return (
              <Card
                key={item.id}
                className={cn('p-4', selectedIds.includes(item.id) && 'border-primary/50')}
                data-testid={`exception-row-${item.id}`}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => toggleOne(item.id)}
                    aria-label={`Select exception ${item.id}`}
                    className="mt-1 rounded border-border"
                  />
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      {statusBadge(item.status)}
                      {signalBadge(item.signal_type)}
                      {item.scheme && <Badge variant="outline">{item.scheme}</Badge>}
                      <span className="font-mono text-xs text-muted-foreground">{item.clause_id}</span>
                      <span className="text-xs text-muted-foreground">
                        {item.entity_type}:{item.entity_id}
                      </span>
                    </div>
                    {item.title && <p className="font-medium text-foreground">{item.title}</p>}
                    {item.rationale && (
                      <p className="text-sm text-muted-foreground">{item.rationale}</p>
                    )}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      {href ? (
                        <Link to={href} className="text-primary hover:underline">
                          Open {entityLabel} #{item.entity_id}
                        </Link>
                      ) : (
                        <span>
                          {entityLabel} #{item.entity_id}
                        </span>
                      )}
                      {item.confidence != null && (
                        <span className="flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          {(item.confidence * 100).toFixed(0)}% confidence
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2 pt-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={acting}
                        data-testid={`exception-confirm-${item.id}`}
                        onClick={() => void handleConfirmOne(item.id)}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> Confirm
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={acting}
                        data-testid={`exception-reject-${item.id}`}
                        onClick={() => void handleRejectOne(item.id)}
                      >
                        <XCircle className="h-3.5 w-3.5" /> Reject
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
