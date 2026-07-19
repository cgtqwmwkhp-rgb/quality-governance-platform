import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info,
  Loader2,
  XCircle,
} from 'lucide-react'
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/Tooltip'
import {
  buildWhyDetail,
  dedupeKnowledgeExceptions,
  resolveClauseIdentity,
  type DedupedExceptionRow,
} from './knowledgeExceptionsHonesty'
import {
  EXCEPTIONS_ENTITY_TYPE_OPTIONS,
  EXCEPTIONS_SIGNAL_TYPE_OPTIONS,
  EXCEPTIONS_STATUS_OPTIONS,
  buildExceptionsInboxSearch,
  exceptionEntityHref,
  exceptionsStatusQueryParam,
  isSafeReturnTo,
  parseExceptionsEntityTypeFilter,
  parseExceptionsSignalTypeFilter,
  parseExceptionsStatusFilter,
  type ExceptionsEntityTypeFilter,
  type ExceptionsSignalTypeFilter,
  type ExceptionsStatusFilter,
} from './exceptionsInboxFilters'

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

const ENTITY_LABELS: Record<string, string> = {
  document: 'Document',
  incident: 'Incident',
  complaint: 'Complaint',
  near_miss: 'Near miss',
  rta: 'RTA',
  audit_finding: 'Audit finding',
}

const allocationBadge = (kind: DedupedExceptionRow['allocationKind'], duplicateCount: number) => {
  if (kind === 'already_confirmed') {
    return <Badge variant="success">Already allocated (confirmed)</Badge>
  }
  if (kind === 'already_rejected') {
    return <Badge variant="destructive">Already decided (rejected)</Badge>
  }
  if (kind === 'duplicate_proposal' && duplicateCount > 0) {
    return (
      <Badge variant="secondary">
        {duplicateCount + 1} proposals collapsed
      </Badge>
    )
  }
  return null
}

const isRowActionable = (kind: DedupedExceptionRow['allocationKind']) =>
  kind === 'actionable' || kind === 'duplicate_proposal'

function ExceptionRow({
  row,
  selected,
  acting,
  onToggle,
  onConfirm,
  onReject,
}: {
  row: DedupedExceptionRow
  selected: boolean
  acting: boolean
  onToggle: () => void
  onConfirm: () => void
  onReject: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const item = row.primary
  const href = exceptionEntityHref(item.entity_type, item.entity_id)
  const entityLabel = ENTITY_LABELS[item.entity_type] ?? item.entity_type
  const identity = resolveClauseIdentity(item)
  const why = buildWhyDetail(item)
  const actionable = isRowActionable(row.allocationKind)

  return (
    <Card
      className={cn('p-4', selected && 'border-primary/50')}
      data-testid={`exception-row-${item.id}`}
      data-allocation-key={row.allocationKey}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={selected}
          disabled={!actionable}
          onChange={onToggle}
          aria-label={`Select exception ${item.id}`}
          className="mt-1 rounded border-border disabled:opacity-40"
        />
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            {statusBadge(item.status)}
            {signalBadge(item.signal_type)}
            {allocationBadge(row.allocationKind, row.duplicates.length)}
          </div>

          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div
                  className="space-y-1 cursor-help rounded-md border border-border/50 bg-muted/20 px-3 py-2"
                  data-testid={`exception-identity-${item.id}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="font-medium">
                      {identity.schemeLabel}
                    </Badge>
                    <span className="font-semibold text-sm text-foreground">
                      Clause {identity.clauseNumber}
                    </span>
                    {identity.clauseTitle ? (
                      <span className="text-sm text-foreground">{identity.clauseTitle}</span>
                    ) : null}
                  </div>
                  {identity.sectionPath ? (
                    <p className="text-xs text-muted-foreground">{identity.sectionPath}</p>
                  ) : null}
                  <p className="text-xs text-muted-foreground font-mono">{identity.rawClauseId}</p>
                </div>
              </TooltipTrigger>
              <TooltipContent
                side="bottom"
                align="start"
                className="max-w-md space-y-1.5 p-3 text-left"
                data-testid={`exception-why-tooltip-${item.id}`}
              >
                <p className="font-medium text-foreground">Why this mapping?</p>
                {why.lines.map((line) => (
                  <p key={line} className="text-xs text-muted-foreground">
                    {line}
                  </p>
                ))}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {item.title && item.title !== identity.clauseTitle ? (
            <p className="font-medium text-foreground">{item.title}</p>
          ) : null}

          <p
            className={cn(
              'text-sm',
              why.isGeneric ? 'text-warning' : 'text-muted-foreground',
            )}
            data-testid={`exception-why-summary-${item.id}`}
          >
            {why.isGeneric ? (
              <span className="inline-flex items-start gap-1">
                <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                {why.summary}
              </span>
            ) : (
              why.summary
            )}
          </p>

          <button
            type="button"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            aria-expanded={expanded}
            data-testid={`exception-detail-toggle-${item.id}`}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? (
              <>
                <ChevronUp className="w-3.5 h-3.5" /> Hide mapping detail
              </>
            ) : (
              <>
                <ChevronDown className="w-3.5 h-3.5" /> Show mapping detail
              </>
            )}
          </button>

          {expanded ? (
            <div
              className="rounded-md border border-border/60 bg-muted/10 p-3 space-y-2 text-xs text-muted-foreground"
              data-testid={`exception-detail-panel-${item.id}`}
            >
              {why.lines.map((line) => (
                <p key={`detail-${line}`}>{line}</p>
              ))}
              {row.duplicates.length > 0 ? (
                <p className="text-warning">
                  Collapsed {row.duplicates.length} duplicate proposal
                  {row.duplicates.length === 1 ? '' : 's'} for the same allocation (
                  {row.allocationKey}).
                </p>
              ) : null}
            </div>
          ) : null}

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

          {actionable ? (
            <div className="flex gap-2 pt-1">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={acting}
                data-testid={`exception-confirm-${item.id}`}
                onClick={onConfirm}
              >
                <CheckCircle2 className="h-3.5 w-3.5" /> Confirm
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={acting}
                data-testid={`exception-reject-${item.id}`}
                onClick={onReject}
              >
                <XCircle className="h-3.5 w-3.5" /> Reject
              </Button>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground pt-1">
              No confirm/reject — this entity is already allocated to{' '}
              {identity.schemeLabel} clause {identity.clauseNumber}.
            </p>
          )}
        </div>
      </div>
    </Card>
  )
}

export default function KnowledgeExceptions() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const clauseFilter = searchParams.get('clause')?.trim() || null
  const standardFilter = searchParams.get('standard')?.trim() || null
  const operationalFromUrl = searchParams.get('operational') === '1'
  const [items, setItems] = useState<KnowledgeEvidenceLink[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [acting, setActing] = useState(false)

  const [statusFilter, setStatusFilter] = useState<ExceptionsStatusFilter>(() =>
    parseExceptionsStatusFilter(searchParams.get('status')),
  )
  const [entityTypeFilter, setEntityTypeFilter] = useState<ExceptionsEntityTypeFilter>(() =>
    parseExceptionsEntityTypeFilter(searchParams.get('entity_type')),
  )
  const [signalTypeFilter, setSignalTypeFilter] = useState<ExceptionsSignalTypeFilter>(() =>
    parseExceptionsSignalTypeFilter(searchParams.get('signal_type')),
  )

  const returnTo = useMemo(() => {
    const raw = searchParams.get('returnTo')
    return isSafeReturnTo(raw) ? raw : null
  }, [searchParams])

  // Hydrate filters from shareable URL.
  useEffect(() => {
    const nextStatus = parseExceptionsStatusFilter(searchParams.get('status'))
    const nextEntity = parseExceptionsEntityTypeFilter(searchParams.get('entity_type'))
    const nextSignal = parseExceptionsSignalTypeFilter(searchParams.get('signal_type'))
    setStatusFilter((prev) => (prev === nextStatus ? prev : nextStatus))
    setEntityTypeFilter((prev) => (prev === nextEntity ? prev : nextEntity))
    setSignalTypeFilter((prev) => (prev === nextSignal ? prev : nextSignal))
  }, [searchParams])

  // Keep status + entity_type + signal_type in the URL (omit defaults); preserve returnTo.
  useEffect(() => {
    const desired = buildExceptionsInboxSearch({
      status: statusFilter,
      entityType: entityTypeFilter,
      signalType: signalTypeFilter,
    })
    const next = new URLSearchParams(searchParams)
    ;['status', 'entity_type', 'signal_type'].forEach((key) => next.delete(key))
    const desiredParams = new URLSearchParams(desired)
    desiredParams.forEach((value, key) => next.set(key, value))
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [statusFilter, entityTypeFilter, signalTypeFilter, searchParams, setSearchParams])

  const loadExceptions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await knowledgeBankApi.listExceptions({
        status: exceptionsStatusQueryParam(statusFilter),
        entityType: entityTypeFilter === 'all' ? undefined : entityTypeFilter,
        signalType: signalTypeFilter === 'all' ? undefined : signalTypeFilter,
        clauseId: clauseFilter || undefined,
        scheme: standardFilter || undefined,
        operationalOnly: operationalFromUrl || undefined,
      })
      setItems(response.data)
      setSelectedIds([])
    } catch (err) {
      setError(reportFailure(err))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [statusFilter, entityTypeFilter, signalTypeFilter, clauseFilter, standardFilter, operationalFromUrl])

  useEffect(() => {
    void loadExceptions()
  }, [loadExceptions])

  /** Server filters status/entity/signal; stable client de-dupe by entity×scheme×clause. */
  const dedupedRows = useMemo(() => dedupeKnowledgeExceptions(items), [items])
  const visibleRows = dedupedRows
  const collapsedDuplicateCount = useMemo(
    () => dedupedRows.reduce((n, row) => n + row.duplicates.length, 0),
    [dedupedRows],
  )

  const actionableRows = useMemo(
    () =>
      visibleRows.filter(
        (row) =>
          row.allocationKind === 'actionable' || row.allocationKind === 'duplicate_proposal',
      ),
    [visibleRows],
  )

  const allSelected = useMemo(
    () =>
      actionableRows.length > 0 &&
      selectedIds.length === actionableRows.length &&
      actionableRows.every((row) => selectedIds.includes(row.primary.id)),
    [actionableRows, selectedIds],
  )

  const returnToCase = useCallback(() => {
    if (returnTo) {
      navigate(returnTo)
    }
  }, [navigate, returnTo])

  const hasActiveFilters =
    statusFilter !== 'inbox' ||
    entityTypeFilter !== 'all' ||
    signalTypeFilter !== 'all' ||
    !!clauseFilter ||
    !!standardFilter ||
    operationalFromUrl

  const clearFilters = useCallback(() => {
    setStatusFilter('inbox')
    setEntityTypeFilter('all')
    setSignalTypeFilter('all')
    setSelectedIds([])
    const next = new URLSearchParams()
    if (returnTo) next.set('returnTo', returnTo)
    setSearchParams(next, { replace: true })
  }, [returnTo, setSearchParams])

  const toggleAll = () => {
    setSelectedIds(
      allSelected ? [] : actionableRows.map((row) => row.primary.id),
    )
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
          {clauseFilter || standardFilter || operationalFromUrl ? (
            <p
              className="text-sm text-primary mt-2"
              data-testid="exceptions-clause-filter-label"
            >
              Filtered from Standards map
              {clauseFilter ? ` · clause ${clauseFilter}` : ''}
              {standardFilter ? ` · standard ${standardFilter}` : ''}
              {operationalFromUrl ? ' · operational signals only' : ''}
            </p>
          ) : null}
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

      <div className="flex flex-col sm:flex-row sm:items-end gap-3 flex-wrap">
        <div className="space-y-1.5 min-w-[12rem]">
          <label htmlFor="exceptions-status" className="text-xs font-medium text-muted-foreground">
            Status
          </label>
          <Select
            value={statusFilter}
            onValueChange={(value) => setStatusFilter(value as ExceptionsStatusFilter)}
          >
            <SelectTrigger id="exceptions-status" aria-label="Filter by status">
              <SelectValue placeholder="Inbox" />
            </SelectTrigger>
            <SelectContent>
              {EXCEPTIONS_STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
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
              {EXCEPTIONS_ENTITY_TYPE_OPTIONS.map((opt) => (
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
              setSignalTypeFilter(value as ExceptionsSignalTypeFilter)
              setSelectedIds([])
            }}
          >
            <SelectTrigger id="exceptions-signal-type" aria-label="Filter by signal type">
              <SelectValue placeholder="All signal types" />
            </SelectTrigger>
            <SelectContent>
              {EXCEPTIONS_SIGNAL_TYPE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <p className="text-xs text-muted-foreground sm:pb-2" data-testid="exceptions-filter-honesty">
          Showing {visibleRows.length} allocation
          {visibleRows.length === 1 ? '' : 's'}
          {items.length !== visibleRows.length
            ? ` (${items.length} server rows; ${collapsedDuplicateCount} duplicate proposal${collapsedDuplicateCount === 1 ? '' : 's'} collapsed)`
            : ''}
          {statusFilter !== 'inbox' ? ` · status=${statusFilter}` : ''}
          {entityTypeFilter !== 'all' ? ` · entity=${entityTypeFilter}` : ''}
          {signalTypeFilter !== 'all' ? ` · signal=${signalTypeFilter}` : ''}
          {' '}(server filters sync to URL; inbox page ≤200 — not a global facet total)
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {error ? null : visibleRows.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 className="w-8 h-8 text-success" />}
          title={hasActiveFilters ? 'No matches for filters' : 'Inbox clear'}
          description={
            hasActiveFilters
              ? 'Server returned no exceptions for these filters on the current inbox page (≤200). This is not a global zero.'
              : 'No proposed or needs-review evidence links at this time.'
          }
          action={
            hasActiveFilters ? (
              <Button
                type="button"
                variant="outline"
                onClick={clearFilters}
                data-testid="exceptions-empty-clear-filters"
              >
                Clear filters
              </Button>
            ) : (
              <Button variant="outline" asChild data-testid="exceptions-empty-open-standards">
                <Link to="/standards">Open standards map</Link>
              </Button>
            )
          }
        />
      ) : (
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-sm text-muted-foreground px-1">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              disabled={actionableRows.length === 0}
              className="rounded border-border disabled:opacity-40"
            />
            Select all actionable
          </label>
          {visibleRows.map((row) => (
            <ExceptionRow
              key={row.primary.id}
              row={row}
              selected={selectedIds.includes(row.primary.id)}
              acting={acting}
              onToggle={() => toggleOne(row.primary.id)}
              onConfirm={() => void handleConfirmOne(row.primary.id)}
              onReject={() => void handleRejectOne(row.primary.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
