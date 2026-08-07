/**
 * Ambient Doc Graph implements thread strip (DG-1).
 *
 * Renders confirmed-only `/thread` hops (title / reference / href) under the
 * document header when `document_graph_thread_ambient` is open. Self-fetches so
 * DocumentDetail only mounts the component — no Golden Thread naming.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, GitBranch, Loader2 } from 'lucide-react'
import { documentGraphApi, getApiErrorMessage } from '../../api/client'
import type { DocumentThreadResponse } from '../../api/documentGraphClient'
import { useFeatureFlag } from '../../hooks/useFeatureFlag'
import { Badge } from '../ui/Badge'
import {
  buildThreadStripItems,
  shouldFetchDocumentThread,
  shouldShowDocumentThreadStrip,
  threadStripHasNeighbors,
} from './documentThreadStripHelpers'

export interface DocumentThreadStripProps {
  documentId: number
  documentTitle: string
  documentReference?: string | null
  /** When false, skip fetch even if ambient flag is on (master Doc Graph closed). */
  documentGraphEnabled?: boolean
}

export function DocumentThreadStrip({
  documentId,
  documentTitle,
  documentReference = null,
  documentGraphEnabled = true,
}: DocumentThreadStripProps) {
  const threadAmbientEnabled = useFeatureFlag('document_graph_thread_ambient')
  const visible = shouldShowDocumentThreadStrip(threadAmbientEnabled)
  const shouldFetch = shouldFetchDocumentThread(documentGraphEnabled, threadAmbientEnabled)

  const [thread, setThread] = useState<DocumentThreadResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!shouldFetch || !documentId || Number.isNaN(documentId)) {
      setThread(null)
      setError(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    setThread(null)

    void (async () => {
      try {
        // Confirmed-only by default — do not pass include_proposed.
        const response = await documentGraphApi.getThread(documentId)
        if (cancelled) return
        setThread(response.data)
      } catch (err) {
        if (cancelled) return
        setThread(null)
        setError(getApiErrorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [documentId, shouldFetch])

  const items = useMemo(
    () =>
      buildThreadStripItems(thread, {
        documentId,
        title: documentTitle,
        reference: documentReference,
      }),
    [thread, documentId, documentTitle, documentReference],
  )

  if (!visible) return null

  const hasNeighbors = threadStripHasNeighbors(items)

  return (
    <div
      className="rounded-xl border border-border bg-card/40 px-3 py-2"
      data-testid="document-thread-strip"
      aria-label="Implements thread"
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <GitBranch className="h-3.5 w-3.5 text-primary" />
        <span className="font-medium text-foreground">Implements thread</span>
        <Badge variant="outline">Confirmed only</Badge>
        <span>Doc Graph spine — not document-control lineage</span>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-1 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          Loading thread…
        </div>
      ) : null}

      {!loading && error ? (
        <p className="text-sm text-destructive" data-testid="document-thread-strip-error">
          {error}
        </p>
      ) : null}

      {!loading && !error && !hasNeighbors ? (
        <p className="text-sm text-muted-foreground" data-testid="document-thread-strip-empty">
          No confirmed implements parents or children recorded for this document.
        </p>
      ) : null}

      {!loading && !error && hasNeighbors ? (
        <nav aria-label="Implements ancestors and descendants">
          <ol
            className="flex flex-wrap items-center gap-1"
            data-testid="document-thread-strip-items"
          >
            {items.map((item, index) => (
              <li key={item.key} className="flex items-center gap-1">
                {index > 0 ? (
                  <ChevronRight
                    className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                    aria-hidden
                  />
                ) : null}
                {item.kind === 'current' ? (
                  <span
                    className="inline-flex max-w-[14rem] flex-col rounded-md bg-primary/10 px-2 py-1"
                    data-testid="document-thread-strip-current"
                  >
                    <span className="truncate text-sm font-semibold text-foreground">
                      {item.title}
                    </span>
                    {item.reference ? (
                      <span className="truncate font-mono text-[10px] text-muted-foreground">
                        {item.reference}
                      </span>
                    ) : null}
                  </span>
                ) : (
                  <Link
                    to={item.href}
                    className="inline-flex max-w-[14rem] flex-col rounded-md px-2 py-1 hover:bg-muted/60"
                    data-testid={`document-thread-strip-hop-${item.documentId}`}
                  >
                    <span className="truncate text-sm font-medium text-foreground underline-offset-2 hover:underline">
                      {item.title}
                    </span>
                    {item.reference ? (
                      <span className="truncate font-mono text-[10px] text-muted-foreground">
                        {item.reference}
                      </span>
                    ) : null}
                  </Link>
                )}
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
    </div>
  )
}

export default DocumentThreadStrip
