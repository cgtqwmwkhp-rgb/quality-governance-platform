import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info,
  Link2,
  Loader2,
  XCircle,
} from 'lucide-react'
import {
  documentGraphApi,
  getApiErrorMessage,
  knowledgeBankApi,
  type KnowledgeEvidenceLink,
} from '../api/client'
import type { PendingDocumentEdgeItem } from '../api/documentGraphClient'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
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
  buildGraphQueueHonesty,
  isBlindPendingEdge,
  isGraphQueueClosedError,
  pendingEdgeHelper,
  pendingEdgeRelationLabel,
  pendingEndpointLabel,
} from './knowledgeExceptionsGraphQueue'
import {
  EXCEPTIONS_ENTITY_TYPE_OPTIONS,
  EXCEPTIONS_GATE_REASON_OPTIONS,
  EXCEPTIONS_SIGNAL_TYPE_OPTIONS,
  EXCEPTIONS_STATUS_OPTIONS,
  buildExceptionsInboxSearch,
  exceptionEntityHref,
  exceptionsStatusQueryParam,
  formatGateReasonLabel,
  isSafeReturnTo,
  parseExceptionsEntityTypeFilter,
  parseExceptionsGateReasonFilter,
  parseExceptionsPage,
  parseExceptionsSignalTypeFilter,
  parseExceptionsStatusFilter,
  unwrapExceptionsInbox,
  type ExceptionsEntityTypeFilter,
  type ExceptionsGateReasonFilter,
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
            {item.gate_reason ? (
              <Badge
                variant="outline"
                data-testid={`exception-gate-reason-${item.id}`}
              >
                {formatGateReasonLabel(item.gate_reason)}
              </Badge>
            ) : null}
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

/**
 * Doc Graph proposals slice of this inbox (WE-1).
 *
 * Reads the tenant-wide confirm queue and acts through the existing Doc Graph
 * edge routes — `document_edges` stays the source of truth and nothing is
 * mirrored into CEL. Deliberately part of this page rather than a twin Confirm
 * Queue route (ADR-0023); the per-document queue on Document Detail → Related
 * remains the other way in.
 */
function GraphProposalsQueue() {
  const graphEnabled = useFeatureFlag('document_graph')
  const [items, setItems] = useState<PendingDocumentEdgeItem[]>([])
  const [page, setPage] = useState({ returned: 0, limit: 200, truncated: false })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [closed, setClosed] = useState(false)
  const [actingEdgeId, setActingEdgeId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    setClosed(false)
    try {
      const response = await documentGraphApi.listPendingEdges()
      setItems(response.data.items)
      setPage({
        returned: response.data.returned,
        limit: response.data.limit,
        truncated: response.data.truncated,
      })
    } catch (err) {
      // A closed flag is not an empty queue, and neither is a failed read.
      setItems([])
      setPage({ returned: 0, limit: 200, truncated: false })
      if (isGraphQueueClosedError(err)) {
        setClosed(true)
      } else {
        setError(getApiErrorMessage(err))
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!graphEnabled) return
    void load()
  }, [graphEnabled, load])

  const honesty = useMemo(() => buildGraphQueueHonesty(page), [page])

  const runAction = async (
    edgeId: number,
    action: () => Promise<unknown>,
    successMessage: string,
  ) => {
    setActingEdgeId(edgeId)
    try {
      await action()
      toast.success(successMessage)
      await load()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setActingEdgeId(null)
    }
  }

  if (!graphEnabled) return null

  return (
    <Card className="p-4 space-y-3" data-testid="exceptions-graph-queue">
      <div className="space-y-1">
        <h2 className="flex items-center gap-2 font-medium text-foreground">
          <Link2 className="w-4 h-4 text-primary" />
          Document relationship proposals
        </h2>
        <p className="text-xs text-muted-foreground">
          Proposed links between two library documents. They do not drive impact until a
          person confirms them. Confirming here is the same decision as confirming on a
          document&apos;s Related tab.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading relationship proposals…
        </div>
      ) : null}

      {!loading && closed ? (
        <p className="text-sm text-muted-foreground" data-testid="exceptions-graph-queue-closed">
          Document Graph is not switched on for this API, so relationship proposals cannot be
          listed. This is not a statement that none are pending.
        </p>
      ) : null}

      {!loading && error ? (
        <div
          className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          data-testid="exceptions-graph-queue-error"
        >
          {error} — relationship proposals could not be listed, so this is not a zero.
        </div>
      ) : null}

      {!loading && !closed && !error ? (
        <>
          <p
            className={cn('text-xs', honesty.truncated ? 'text-warning' : 'text-muted-foreground')}
            data-testid="exceptions-graph-queue-honesty"
          >
            {honesty.summary}
          </p>
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="exceptions-graph-queue-empty">
              No relationship proposals awaiting confirmation. Propose links from a
              document&apos;s Related tab.
            </p>
          ) : (
            <div className="space-y-2">
              {items.map((item) => {
                const blind = isBlindPendingEdge(item)
                // Page-wide, matching the CEL rows above: one decision in flight at a
                // time, so a second click cannot land against a list this reload will
                // replace.
                const busy = actingEdgeId !== null
                return (
                  <div
                    key={item.edge_id}
                    className="rounded-lg border border-border bg-card/40 p-3 space-y-2"
                    data-testid={`graph-proposal-row-${item.edge_id}`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      {statusBadge(item.status)}
                      <Badge variant="outline">{pendingEdgeRelationLabel(item.edge_type)}</Badge>
                      {item.is_primary_parent ? (
                        <Badge variant="secondary">Primary parent</Badge>
                      ) : null}
                      {item.created_method !== 'manual' ? (
                        <Badge variant="outline">{item.created_method}</Badge>
                      ) : null}
                      {item.impact_driving ? (
                        <Badge
                          variant="warning"
                          data-testid={`graph-proposal-impact-${item.edge_id}`}
                        >
                          Drives publish impact once confirmed
                        </Badge>
                      ) : null}
                    </div>

                    <p className="text-sm text-foreground">
                      {item.src.readable ? (
                        <Link to={item.src.href} className="text-primary hover:underline">
                          {pendingEndpointLabel(item.src)}
                        </Link>
                      ) : (
                        <span>{pendingEndpointLabel(item.src)}</span>
                      )}
                      <span className="text-muted-foreground">
                        {' '}
                        {pendingEdgeRelationLabel(item.edge_type).toLowerCase()}{' '}
                      </span>
                      {item.dst.readable ? (
                        <Link to={item.dst.href} className="text-primary hover:underline">
                          {pendingEndpointLabel(item.dst)}
                        </Link>
                      ) : (
                        <span>{pendingEndpointLabel(item.dst)}</span>
                      )}
                    </p>

                    <p className="text-xs text-muted-foreground">
                      {item.rationale?.trim() || pendingEdgeHelper(item.edge_type)}
                      {item.confidence != null
                        ? ` · ${(item.confidence * 100).toFixed(0)}% confidence`
                        : ''}
                    </p>

                    {blind ? (
                      <p
                        className="text-xs text-warning"
                        data-testid={`graph-proposal-blind-${item.edge_id}`}
                      >
                        Neither document is available to you, so this proposal is not yours to
                        decide. Ask a platform admin for access.
                      </p>
                    ) : (
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          data-testid={`graph-proposal-confirm-${item.edge_id}`}
                          onClick={() =>
                            void runAction(
                              item.edge_id,
                              () => documentGraphApi.confirmEdge(item.edge_id),
                              'Relationship confirmed',
                            )
                          }
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" /> Confirm
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={busy}
                          data-testid={`graph-proposal-reject-${item.edge_id}`}
                          onClick={() =>
                            void runAction(
                              item.edge_id,
                              () => documentGraphApi.rejectEdge(item.edge_id),
                              'Relationship rejected',
                            )
                          }
                        >
                          <XCircle className="h-3.5 w-3.5" /> Reject
                        </Button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </>
      ) : null}
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
  const [inboxPage, setInboxPage] = useState(() => parseExceptionsPage(searchParams.get('page')))
  const [inboxMeta, setInboxMeta] = useState({
    page: 1,
    page_size: 200,
    truncated: false,
    has_next: false,
    has_prev: false,
  })
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
  const [gateReasonFilter, setGateReasonFilter] = useState<ExceptionsGateReasonFilter>(() =>
    parseExceptionsGateReasonFilter(searchParams.get('gate_reason')),
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
    const nextGate = parseExceptionsGateReasonFilter(searchParams.get('gate_reason'))
    const nextPage = parseExceptionsPage(searchParams.get('page'))
    setStatusFilter((prev) => (prev === nextStatus ? prev : nextStatus))
    setEntityTypeFilter((prev) => (prev === nextEntity ? prev : nextEntity))
    setSignalTypeFilter((prev) => (prev === nextSignal ? prev : nextSignal))
    setGateReasonFilter((prev) => (prev === nextGate ? prev : nextGate))
    setInboxPage((prev) => (prev === nextPage ? prev : nextPage))
  }, [searchParams])

  // Keep status + entity_type + signal_type in the URL (omit defaults); preserve returnTo.
  useEffect(() => {
    const desired = buildExceptionsInboxSearch({
      status: statusFilter,
      entityType: entityTypeFilter,
      signalType: signalTypeFilter,
      gateReason: gateReasonFilter,
      page: inboxPage,
    })
    const next = new URLSearchParams(searchParams)
    ;['status', 'entity_type', 'signal_type', 'gate_reason', 'page'].forEach((key) => next.delete(key))
    const desiredParams = new URLSearchParams(desired)
    desiredParams.forEach((value, key) => next.set(key, value))
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [statusFilter, entityTypeFilter, signalTypeFilter, gateReasonFilter, inboxPage, searchParams, setSearchParams])

  const loadExceptions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await knowledgeBankApi.listExceptions({
        status: exceptionsStatusQueryParam(statusFilter),
        entityType: entityTypeFilter === 'all' ? undefined : entityTypeFilter,
        signalType: signalTypeFilter === 'all' ? undefined : signalTypeFilter,
        gateReason: gateReasonFilter === 'all' ? undefined : gateReasonFilter,
        clauseId: clauseFilter || undefined,
        scheme: standardFilter || undefined,
        operationalOnly: operationalFromUrl || undefined,
        page: inboxPage,
      })
      const page = unwrapExceptionsInbox(response.data)
      setItems(page.items)
      setInboxMeta({
        page: page.page,
        page_size: page.page_size,
        truncated: page.truncated,
        has_next: page.has_next,
        has_prev: page.has_prev,
      })
      setSelectedIds([])
    } catch (err) {
      setError(reportFailure(err))
      setItems([])
      setInboxMeta({ page: inboxPage, page_size: 200, truncated: false, has_next: false, has_prev: inboxPage > 1 })
    } finally {
      setLoading(false)
    }
  }, [statusFilter, entityTypeFilter, signalTypeFilter, gateReasonFilter, clauseFilter, standardFilter, operationalFromUrl, inboxPage])

  useEffect(() => {
    void loadExceptions()
  }, [loadExceptions])

  /** Server filters status/entity/signal/gate_reason; stable client de-dupe by entity×scheme×clause. */
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
    gateReasonFilter !== 'all' ||
    !!clauseFilter ||
    !!standardFilter ||
    operationalFromUrl

  const clearFilters = useCallback(() => {
    setStatusFilter('inbox')
    setEntityTypeFilter('all')
    setSignalTypeFilter('all')
    setGateReasonFilter('all')
    setInboxPage(1)
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
          panel, then run <strong>Map to ISO clauses</strong> (complaints: ISO / UVDB). Proposed
          links land here for confirm/reject (reject requires a rationale). Planet Mark is not
          mapped from cases.
        </p>
      </Card>

      <GraphProposalsQueue />

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
            onValueChange={(value) => {
              setStatusFilter(value as ExceptionsStatusFilter)
              setInboxPage(1)
            }}
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
            onValueChange={(value) => {
              setEntityTypeFilter(value as ExceptionsEntityTypeFilter)
              setInboxPage(1)
            }}
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
              setInboxPage(1)
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
        <div className="space-y-1.5 min-w-[14rem]">
          <label htmlFor="exceptions-gate-reason" className="text-xs font-medium text-muted-foreground">
            Ingest gate reason
          </label>
          <Select
            value={gateReasonFilter}
            onValueChange={(value) => {
              setGateReasonFilter(value as ExceptionsGateReasonFilter)
              setInboxPage(1)
              setSelectedIds([])
            }}
          >
            <SelectTrigger id="exceptions-gate-reason" aria-label="Filter by ingest gate reason">
              <SelectValue placeholder="All ingest gate reasons" />
            </SelectTrigger>
            <SelectContent>
              {EXCEPTIONS_GATE_REASON_OPTIONS.map((opt) => (
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
          {gateReasonFilter !== 'all' ? ` · gate=${gateReasonFilter}` : ''}
          {` · page ${inboxMeta.page} of up to ${inboxMeta.page_size} — not a global total`}
          {inboxMeta.truncated ? ' · more pages follow' : ''}
          {' '}(server filters sync to URL)
        </p>
      </div>

      <div className="flex items-center gap-2" data-testid="exceptions-pager">
        <Button
          variant="outline"
          size="sm"
          disabled={!inboxMeta.has_prev || acting}
          onClick={() => setInboxPage((p) => Math.max(1, p - 1))}
          data-testid="exceptions-page-prev"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!inboxMeta.has_next || acting}
          onClick={() => setInboxPage((p) => p + 1)}
          data-testid="exceptions-page-next"
        >
          Next
        </Button>
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
                <Link to="/compliance?view=matrix">Open standards map</Link>
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
