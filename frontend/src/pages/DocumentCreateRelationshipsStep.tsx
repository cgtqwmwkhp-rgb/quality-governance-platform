/**
 * Post-upload Doc Graph step (ADR-0021 Wave 1 PR-C).
 *
 * Shown after a library Document is created when `document_graph` is open.
 * Captures implements / requires_record / related_to / conflicts_with via the
 * existing create-edge API. Never calls Doc Graph the Golden Thread.
 */
import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Link2, Loader2, Search, XCircle } from 'lucide-react'
import api, { documentGraphApi, getApiErrorMessage } from '../api/client'
import type { DocumentEdge, DocumentEdgeType } from '../api/documentGraphClient'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Badge } from '../components/ui/Badge'
import {
  buildDocumentEdgePayload,
  CREATE_WIZARD_DOCUMENT_EDGE_TYPES,
  DOCUMENT_EDGE_TYPE_META,
  findConflictingEdge,
  type DocumentEdgeDirection,
} from './documentRelationshipHelpers'

interface CounterpartDocument {
  id: number
  title: string
  reference_number?: string | null
  status?: string | null
}

export interface DocumentCreateRelationshipsStepProps {
  documentId: number
  documentTitle: string
  onDone: () => void
}

export function DocumentCreateRelationshipsStep({
  documentId,
  documentTitle,
  onDone,
}: DocumentCreateRelationshipsStepProps) {
  const [edges, setEdges] = useState<DocumentEdge[]>([])
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<CounterpartDocument[]>([])
  const [searching, setSearching] = useState(false)
  const [target, setTarget] = useState<CounterpartDocument | null>(null)
  const [edgeType, setEdgeType] = useState<DocumentEdgeType>('implements')
  const [direction, setDirection] = useState<Exclude<DocumentEdgeDirection, 'peer'>>('outbound')
  const [isPrimaryParent, setIsPrimaryParent] = useState(true)
  const [rationale, setRationale] = useState('')
  const [linking, setLinking] = useState(false)
  const [recorded, setRecorded] = useState<
    { edge: DocumentEdge; counterpartTitle: string; relationLabel: string }[]
  >([])

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

  const handleLink = async () => {
    if (!draftPayload || duplicateEdge || !target) return
    setLinking(true)
    try {
      const response = await documentGraphApi.createEdge(draftPayload)
      const edge = response.data
      const relationLabel =
        DOCUMENT_EDGE_TYPE_META[edge.edge_type].directed &&
        edge.dst_document_id === documentId
          ? DOCUMENT_EDGE_TYPE_META[edge.edge_type].inbound
          : DOCUMENT_EDGE_TYPE_META[edge.edge_type].outbound
      setEdges((prev) => [...prev, edge])
      setRecorded((prev) => [
        ...prev,
        { edge, counterpartTitle: target.title, relationLabel },
      ])
      toast.success('Relationship recorded')
      setTarget(null)
      setSearch('')
      setSearchResults([])
      setRationale('')
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setLinking(false)
    }
  }

  return (
    <div className="space-y-4" data-testid="documents-create-relationships-step">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-lg bg-primary/10 p-2">
          <Link2 className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0 space-y-1">
          <h3 className="font-medium text-foreground">Document relationships</h3>
          <p className="text-sm text-muted-foreground">
            What does <span className="font-medium text-foreground">{documentTitle}</span>{' '}
            implement, require, relate to, or conflict with? These links are authored
            relationships between library documents — they do not change version control
            lineage.
          </p>
        </div>
      </div>

      {recorded.length > 0 ? (
        <ul
          className="space-y-2 rounded-lg border border-border p-3"
          data-testid="documents-create-relationships-recorded"
        >
          {recorded.map(({ edge, counterpartTitle, relationLabel }) => (
            <li
              key={edge.id}
              className="flex flex-wrap items-center gap-2 text-sm"
              data-testid={`documents-create-relationship-${edge.id}`}
            >
              <Badge variant="outline">{relationLabel}</Badge>
              <span className="font-medium text-foreground">{counterpartTitle}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {target ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card/40 p-3">
          <span className="font-medium text-foreground" data-testid="documents-create-rel-target">
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
            data-testid="documents-create-rel-clear-target"
          >
            <XCircle className="mr-1 h-4 w-4" />
            Change
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          <label className="text-sm text-muted-foreground" htmlFor="documents-create-rel-search">
            Find a document
          </label>
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              id="documents-create-rel-search"
              placeholder="Search the library by title or reference"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              data-testid="documents-create-rel-search"
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
                    data-testid={`documents-create-rel-result-${item.id}`}
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
            <p className="text-sm text-muted-foreground" data-testid="documents-create-rel-no-results">
              No matching documents.
            </p>
          ) : null}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label className="text-sm text-muted-foreground" htmlFor="documents-create-rel-type">
            Relationship
          </label>
          <select
            id="documents-create-rel-type"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={edgeType}
            onChange={(e) => setEdgeType(e.target.value as DocumentEdgeType)}
            data-testid="documents-create-rel-type"
          >
            {CREATE_WIZARD_DOCUMENT_EDGE_TYPES.map((type) => (
              <option key={type} value={type}>
                {DOCUMENT_EDGE_TYPE_META[type].label}
              </option>
            ))}
          </select>
        </div>
        {meta.directed ? (
          <div className="space-y-1">
            <label
              className="text-sm text-muted-foreground"
              htmlFor="documents-create-rel-direction"
            >
              Direction
            </label>
            <select
              id="documents-create-rel-direction"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={direction}
              onChange={(e) =>
                setDirection(e.target.value as Exclude<DocumentEdgeDirection, 'peer'>)
              }
              data-testid="documents-create-rel-direction"
            >
              <option value="outbound">This document {meta.outbound.toLowerCase()} it</option>
              <option value="inbound">It {meta.outbound.toLowerCase()} this document</option>
            </select>
          </div>
        ) : null}
      </div>

      <p className="text-xs text-muted-foreground" data-testid="documents-create-rel-helper">
        {meta.helper}
      </p>

      {edgeType === 'implements' ? (
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={isPrimaryParent}
            onChange={(e) => setIsPrimaryParent(e.target.checked)}
            data-testid="documents-create-rel-primary-parent"
          />
          Primary parent — the single document this one most directly carries out
        </label>
      ) : null}

      <Textarea
        placeholder="Why are these documents related? (optional)"
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
        rows={2}
        data-testid="documents-create-rel-rationale"
      />

      {duplicateEdge ? (
        <p
          className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400"
          data-testid="documents-create-rel-duplicate"
        >
          <AlertTriangle className="h-4 w-4" />
          This relationship already exists for this upload.
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <Button
          onClick={() => void handleLink()}
          disabled={!draftPayload || Boolean(duplicateEdge) || linking}
          data-testid="documents-create-rel-submit"
        >
          {linking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Record relationship
        </Button>
        <Button
          variant="secondary"
          onClick={onDone}
          data-testid="documents-create-rel-done"
        >
          {recorded.length > 0 ? 'Done' : 'Skip for now'}
        </Button>
      </div>
    </div>
  )
}

export default DocumentCreateRelationshipsStep
