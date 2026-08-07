import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  CheckCircle2,
  Link2,
  Loader2,
  Search,
  Trash2,
  XCircle,
} from 'lucide-react'
import api, { documentGraphApi, getApiErrorMessage, type DocumentEdge } from '../api/client'
import type { DocumentEdgeType } from '../api/documentGraphClient'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { EmptyState } from '../components/ui/EmptyState'
import {
  buildDocumentEdgePayload,
  counterpartDocumentIds,
  DOCUMENT_EDGE_TYPE_META,
  DOCUMENT_EDGE_TYPES,
  findConflictingEdge,
  isPendingDocumentEdge,
  resolveDocumentEdges,
  summariseDocumentRelationships,
  type DocumentEdgeDirection,
  type ResolvedDocumentEdge,
} from './documentRelationshipHelpers'

interface CounterpartDocument {
  id: number
  title: string
  reference_number?: string | null
  status?: string | null
  pel_doc_ref?: string | null
}

export interface DocumentRelationshipsPanelProps {
  documentId: number
  documentTitle: string
  edges: DocumentEdge[]
  loading: boolean
  error: string | null
  onChanged: () => Promise<void> | void
}

const statusBadge = (edge: DocumentEdge) => {
  switch (edge.status) {
    case 'confirmed':
      return <Badge variant="success">Confirmed</Badge>
    case 'proposed':
      return <Badge variant="submitted">Proposed</Badge>
    case 'needs_review':
      return <Badge variant="warning">Needs review</Badge>
    case 'rejected':
      return <Badge variant="destructive">Rejected</Badge>
    default:
      return <Badge variant="secondary">{edge.status}</Badge>
  }
}

export function DocumentRelationshipsPanel({
  documentId,
  documentTitle,
  edges,
  loading,
  error,
  onChanged,
}: DocumentRelationshipsPanelProps) {
  const [counterparts, setCounterparts] = useState<Record<number, CounterpartDocument | null>>({})
  const requestedRef = useRef<Set<number>>(new Set())

  const [busyEdgeId, setBusyEdgeId] = useState<number | null>(null)
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<number[]>([])
  const [bulkConfirming, setBulkConfirming] = useState(false)

  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<CounterpartDocument[]>([])
  const [searching, setSearching] = useState(false)
  const [target, setTarget] = useState<CounterpartDocument | null>(null)
  const [edgeType, setEdgeType] = useState<DocumentEdgeType>('implements')
  const [direction, setDirection] = useState<Exclude<DocumentEdgeDirection, 'peer'>>('outbound')
  const [isPrimaryParent, setIsPrimaryParent] = useState(true)
  const [rationale, setRationale] = useState('')
  const [linking, setLinking] = useState(false)

  const resolved = useMemo(() => resolveDocumentEdges(documentId, edges), [documentId, edges])
  const summary = useMemo(
    () => summariseDocumentRelationships(documentId, edges),
    [documentId, edges],
  )

  const pending = useMemo(
    () => resolved.filter((item) => isPendingDocumentEdge(item.edge)),
    [resolved],
  )
  const confirmed = useMemo(
    () => resolved.filter((item) => item.edge.status === 'confirmed'),
    [resolved],
  )
  const rejected = useMemo(
    () => resolved.filter((item) => item.edge.status === 'rejected' && !item.edge.deleted_at),
    [resolved],
  )

  useEffect(() => {
    requestedRef.current = new Set()
    setCounterparts({})
    setSelectedEdgeIds([])
  }, [documentId])

  // Edge payloads carry ids, not titles. Resolve each counterpart once through the
  // library endpoint so per-document ACLs still decide what the operator may read.
  useEffect(() => {
    const needed = counterpartDocumentIds(documentId, edges).filter(
      (id) => !requestedRef.current.has(id),
    )
    if (needed.length === 0) return
    needed.forEach((id) => requestedRef.current.add(id))

    let cancelled = false
    void (async () => {
      const entries = await Promise.all(
        needed.map(async (id) => {
          try {
            const response = await api.get<CounterpartDocument>(`/api/v1/documents/${id}`)
            return [id, response.data] as const
          } catch {
            return [id, null] as const
          }
        }),
      )
      if (cancelled) return
      setCounterparts((prev) => ({ ...prev, ...Object.fromEntries(entries) }))
    })()

    return () => {
      cancelled = true
    }
  }, [documentId, edges])

  useEffect(() => {
    const term = search.trim()
    if (term.length < 2) {
      setSearchResults([])
      setSearching(false)
      return
    }
    setSearching(true)
    let cancelled = false
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const response = await api.get<{ items: CounterpartDocument[] }>('/api/v1/documents/', {
            params: { search: term, page_size: 8 },
          })
          if (cancelled) return
          setSearchResults(response.data.items.filter((item) => item.id !== documentId))
        } catch (err) {
          if (cancelled) return
          setSearchResults([])
          toast.error(getApiErrorMessage(err))
        } finally {
          if (!cancelled) setSearching(false)
        }
      })()
    }, 300)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [search, documentId])

  const meta = DOCUMENT_EDGE_TYPE_META[edgeType]

  const draftPayload = useMemo(() => {
    if (!target) return null
    try {
      return buildDocumentEdgePayload({
        documentId,
        counterpartDocumentId: target.id,
        edgeType,
        direction,
        isPrimaryParent: edgeType === 'implements' && isPrimaryParent,
        rationale,
      })
    } catch {
      return null
    }
  }, [documentId, target, edgeType, direction, isPrimaryParent, rationale])

  const duplicateEdge = useMemo(
    () => (draftPayload ? findConflictingEdge(edges, draftPayload) : null),
    [edges, draftPayload],
  )

  const counterpartName = useCallback(
    (item: ResolvedDocumentEdge) => {
      const doc = counterparts[item.counterpartDocumentId]
      if (doc) return doc.title
      if (item.counterpartDocumentId in counterparts) {
        return item.counterpartPelDocRef
          ? `${item.counterpartPelDocRef} — not available to you`
          : `Document #${item.counterpartDocumentId} — not available to you`
      }
      return item.counterpartPelDocRef ?? `Document #${item.counterpartDocumentId}`
    },
    [counterparts],
  )

  const runEdgeAction = async (
    edgeId: number,
    action: () => Promise<unknown>,
    successMessage: string,
  ) => {
    setBusyEdgeId(edgeId)
    try {
      await action()
      toast.success(successMessage)
      setSelectedEdgeIds((prev) => prev.filter((id) => id !== edgeId))
      await onChanged()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setBusyEdgeId(null)
    }
  }

  const handleBulkConfirm = async () => {
    if (selectedEdgeIds.length === 0) return
    setBulkConfirming(true)
    try {
      const result = await documentGraphApi.confirmEdges(selectedEdgeIds)
      if (result.confirmed.length > 0) {
        toast.success(`Confirmed ${result.confirmed.length} relationship(s)`)
      }
      if (result.failed.length > 0) {
        toast.error(
          `${result.failed.length} relationship(s) could not be confirmed — ${getApiErrorMessage(
            result.failed[0].error,
          )}`,
        )
      }
      setSelectedEdgeIds([])
      await onChanged()
    } finally {
      setBulkConfirming(false)
    }
  }

  const handleLink = async () => {
    if (!draftPayload || duplicateEdge) return
    setLinking(true)
    try {
      await documentGraphApi.createEdge(draftPayload)
      toast.success('Relationship recorded')
      setTarget(null)
      setSearch('')
      setSearchResults([])
      setRationale('')
      await onChanged()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setLinking(false)
    }
  }

  const toggleSelection = (edgeId: number) => {
    setSelectedEdgeIds((prev) =>
      prev.includes(edgeId) ? prev.filter((id) => id !== edgeId) : [...prev, edgeId],
    )
  }

  const renderRow = (item: ResolvedDocumentEdge, options: { selectable?: boolean } = {}) => {
    const { edge } = item
    const busy = busyEdgeId === edge.id
    const isConflict = edge.edge_type === 'conflicts_with'
    return (
      <div
        key={edge.id}
        className={
          isConflict
            ? 'rounded-lg border border-destructive/40 bg-destructive/5 p-3'
            : 'rounded-lg border border-border bg-card/40 p-3'
        }
        data-testid={`relationship-row-${edge.id}`}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              {options.selectable ? (
                <input
                  type="checkbox"
                  checked={selectedEdgeIds.includes(edge.id)}
                  onChange={() => toggleSelection(edge.id)}
                  aria-label={`Select relationship ${edge.id}`}
                  className="rounded border-border"
                />
              ) : null}
              <Badge variant="outline">{item.relationLabel}</Badge>
              {statusBadge(edge)}
              {edge.is_primary_parent ? <Badge variant="secondary">Primary parent</Badge> : null}
              {edge.created_method !== 'manual' ? (
                <Badge variant="outline">{edge.created_method}</Badge>
              ) : null}
            </div>
            <p className="font-medium text-foreground truncate">
              <Link
                to={`/documents/${item.counterpartDocumentId}`}
                className="hover:underline"
                data-testid={`relationship-link-${edge.id}`}
              >
                {counterpartName(item)}
              </Link>
            </p>
            {edge.rationale ? (
              <p className="text-sm text-muted-foreground">{edge.rationale}</p>
            ) : null}
            {edge.confidence != null ? (
              <p className="text-xs text-muted-foreground">
                Confidence: {(edge.confidence * 100).toFixed(0)}%
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {isPendingDocumentEdge(edge) ? (
              <>
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    void runEdgeAction(
                      edge.id,
                      () => documentGraphApi.confirmEdge(edge.id),
                      'Relationship confirmed',
                    )
                  }
                  data-testid={`relationship-confirm-${edge.id}`}
                >
                  {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Confirm
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() =>
                    void runEdgeAction(
                      edge.id,
                      () => documentGraphApi.rejectEdge(edge.id),
                      'Relationship rejected',
                    )
                  }
                  data-testid={`relationship-reject-${edge.id}`}
                >
                  Reject
                </Button>
              </>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() =>
                void runEdgeAction(
                  edge.id,
                  () => documentGraphApi.deleteEdge(edge.id),
                  'Relationship removed',
                )
              }
              title="Remove this relationship (keeps the audit record)"
              data-testid={`relationship-unlink-${edge.id}`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (loading && edges.length === 0) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-4" data-testid="document-relationships-panel">
      {error ? (
        <div
          className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          data-testid="relationships-error"
        >
          {error}
        </div>
      ) : null}

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className="flex items-center gap-2 font-medium text-foreground">
            <Link2 className="h-4 w-4 text-primary" />
            {summary.confirmed} confirmed relationship{summary.confirmed === 1 ? '' : 's'}
          </span>
          <span className="text-muted-foreground" data-testid="relationships-breakdown">
            {summary.outbound} from this document · {summary.inbound} to this document ·{' '}
            {summary.peers} peer
          </span>
          {summary.pending > 0 ? (
            <Badge variant="warning" data-testid="relationships-pending-count">
              {summary.pending} awaiting confirmation
            </Badge>
          ) : null}
          {summary.conflicts > 0 ? (
            <Badge variant="destructive" data-testid="relationships-conflict-count">
              {summary.conflicts} conflict{summary.conflicts === 1 ? '' : 's'}
            </Badge>
          ) : null}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Coverage is only what has been recorded here. An empty or thin list means this
          document&rsquo;s place in the governance hierarchy is unknown, not that it has none.
        </p>
      </Card>

      {pending.length > 0 ? (
        <Card className="p-4 space-y-3" data-testid="relationships-confirm-queue">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h4 className="font-medium text-foreground">Awaiting confirmation</h4>
              <p className="text-xs text-muted-foreground">
                Proposed relationships do not drive impact until a person confirms them.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  setSelectedEdgeIds(
                    selectedEdgeIds.length === pending.length
                      ? []
                      : pending.map((item) => item.edge.id),
                  )
                }
                data-testid="relationships-select-all"
              >
                {selectedEdgeIds.length === pending.length ? 'Clear selection' : 'Select all'}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={selectedEdgeIds.length === 0 || bulkConfirming}
                onClick={() => void handleBulkConfirm()}
                data-testid="relationships-bulk-confirm"
              >
                {bulkConfirming ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                )}
                Confirm selected ({selectedEdgeIds.length})
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            {pending.map((item) => renderRow(item, { selectable: true }))}
          </div>
        </Card>
      ) : null}

      {confirmed.length === 0 && pending.length === 0 ? (
        <EmptyState
          icon={<Link2 className="h-8 w-8 text-muted-foreground" />}
          title="No relationships recorded"
          description={`Link ${documentTitle} to the documents it implements, the records it requires, or the documents it references. These links are separate from document control lineage.`}
        />
      ) : null}

      {confirmed.length > 0 ? (
        <Card className="p-4 space-y-2" data-testid="relationships-confirmed-list">
          <h4 className="font-medium text-foreground">Confirmed relationships</h4>
          <div className="space-y-2">{confirmed.map((item) => renderRow(item))}</div>
        </Card>
      ) : null}

      <Card className="p-4 space-y-3" data-testid="relationships-add-form">
        <div>
          <h4 className="font-medium text-foreground">Link another document</h4>
          <p className="text-xs text-muted-foreground">
            Records a relationship between two library documents. It does not change either
            document&rsquo;s version, approval state or file.
          </p>
        </div>

        {target ? (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card/40 p-3">
            <span className="font-medium text-foreground" data-testid="relationships-target">
              {target.title}
            </span>
            {target.reference_number ? (
              <span className="font-mono text-xs text-muted-foreground">
                {target.reference_number}
              </span>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setTarget(null)}
              data-testid="relationships-clear-target"
            >
              <XCircle className="mr-1 h-4 w-4" />
              Change
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground" htmlFor="relationships-search">
              Find a document
            </label>
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-muted-foreground" />
              <Input
                id="relationships-search"
                placeholder="Search the library by title or reference"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                data-testid="relationships-search"
              />
              {searching ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : null}
            </div>
            {searchResults.length > 0 ? (
              <ul className="divide-y divide-border rounded-lg border border-border">
                {searchResults.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="flex w-full flex-wrap items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted/50"
                      onClick={() => setTarget(item)}
                      data-testid={`relationships-search-result-${item.id}`}
                    >
                      <span className="font-medium text-foreground">{item.title}</span>
                      {item.reference_number ? (
                        <span className="font-mono text-xs text-muted-foreground">
                          {item.reference_number}
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            {!searching && search.trim().length >= 2 && searchResults.length === 0 ? (
              <p className="text-sm text-muted-foreground" data-testid="relationships-no-results">
                No matching documents.
              </p>
            ) : null}
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-sm text-muted-foreground" htmlFor="relationships-type">
              Relationship
            </label>
            <select
              id="relationships-type"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={edgeType}
              onChange={(e) => setEdgeType(e.target.value as DocumentEdgeType)}
              data-testid="relationships-type"
            >
              {DOCUMENT_EDGE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {DOCUMENT_EDGE_TYPE_META[type].label}
                </option>
              ))}
            </select>
          </div>
          {meta.directed ? (
            <div className="space-y-1">
              <label className="text-sm text-muted-foreground" htmlFor="relationships-direction">
                Direction
              </label>
              <select
                id="relationships-direction"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={direction}
                onChange={(e) =>
                  setDirection(e.target.value as Exclude<DocumentEdgeDirection, 'peer'>)
                }
                data-testid="relationships-direction"
              >
                <option value="outbound">This document {meta.outbound.toLowerCase()} it</option>
                <option value="inbound">It {meta.outbound.toLowerCase()} this document</option>
              </select>
            </div>
          ) : null}
        </div>

        <p className="text-xs text-muted-foreground" data-testid="relationships-type-helper">
          {meta.helper}
        </p>

        {edgeType === 'implements' ? (
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={isPrimaryParent}
              onChange={(e) => setIsPrimaryParent(e.target.checked)}
              data-testid="relationships-primary-parent"
            />
            Primary parent — the single document this one most directly carries out
          </label>
        ) : null}

        <Textarea
          placeholder="Why are these documents related? (optional)"
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={2}
          data-testid="relationships-rationale"
        />

        {duplicateEdge ? (
          <p
            className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400"
            data-testid="relationships-duplicate-warning"
          >
            <AlertTriangle className="h-4 w-4" />
            {duplicateEdge.status === 'rejected'
              ? 'This relationship was rejected before. Remove the rejected entry below to record it again.'
              : 'This relationship already exists.'}
          </p>
        ) : null}

        <Button
          onClick={() => void handleLink()}
          disabled={!draftPayload || Boolean(duplicateEdge) || linking}
          data-testid="relationships-submit"
        >
          {linking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Record relationship
        </Button>
      </Card>

      {rejected.length > 0 ? (
        <Card className="p-4 space-y-2" data-testid="relationships-rejected-list">
          <h4 className="font-medium text-foreground">Rejected</h4>
          <p className="text-xs text-muted-foreground">
            Kept on record. Remove an entry to free the pair so it can be proposed again.
          </p>
          <div className="space-y-2">{rejected.map((item) => renderRow(item))}</div>
        </Card>
      ) : null}
    </div>
  )
}

export default DocumentRelationshipsPanel
