/**
 * ISO reverse freshness panel (Doc Graph Wave 1 PR-F).
 *
 * Flag-gated by the caller (`document_graph`). Shows library documents
 * evidencing the selected clause with CEL tip freshness and deep-links to
 * `/documents/:id?tab=evidence`. Never called “golden thread.”
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, FileText } from 'lucide-react'
import {
  documentGraphApi,
  getApiErrorMessage,
  type ClauseDocumentFreshnessItem,
} from '../api/client'
import { Badge } from '../components/ui'
import { documentEvidenceHref } from './documentEvidenceTab'
import {
  clauseDocumentFreshnessLabel,
  clauseDocumentFreshnessTone,
} from './complianceEvidenceHelpers'

export interface ClauseDocumentsFreshnessPanelProps {
  clauseId: string
  enabled: boolean
}

export function ClauseDocumentsFreshnessPanel({
  clauseId,
  enabled,
}: ClauseDocumentsFreshnessPanelProps) {
  const [items, setItems] = useState<ClauseDocumentFreshnessItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled || !clauseId) {
      setItems([])
      setError(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    void documentGraphApi
      .listClauseDocuments(clauseId)
      .then((response) => {
        if (cancelled) return
        setItems(response.data.documents ?? [])
      })
      .catch((err: unknown) => {
        if (cancelled) return
        // Soft-fail: reverse freshness is additive; Linked Evidence still works.
        setItems([])
        setError(getApiErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [clauseId, enabled])

  if (!enabled) return null

  return (
    <div className="space-y-2" data-testid="clause-documents-freshness">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-muted-foreground">
          Library documents (version freshness)
        </h4>
        <span className="text-xs text-muted-foreground">
          {loading ? 'Loading…' : `${items.length} document link(s)`}
        </span>
      </div>
      {error ? (
        <div
          className="p-3 bg-warning/10 rounded-lg border border-warning/30"
          role="status"
          data-testid="clause-documents-freshness-error"
        >
          <p className="text-sm text-warning font-medium">Freshness unavailable</p>
          <p className="text-xs text-muted-foreground mt-1">{error}</p>
        </div>
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <div className="p-4 bg-surface/50 rounded-lg border border-border text-center">
          <p className="text-sm text-muted-foreground">
            No library documents linked to this clause yet.
          </p>
        </div>
      ) : null}
      {items.length > 0 ? (
        <div className="space-y-2">
          {items.map((doc) => {
            const href =
              doc.document_id != null ? documentEvidenceHref(doc.document_id) : null
            const tipNote = doc.tip_version_number
              ? `Tip v${doc.tip_version_number}`
              : doc.pinned_document_version_id != null
                ? `Pinned version #${doc.pinned_document_version_id}`
                : 'No version pin'
            return (
              <div
                key={doc.evidence_link_id}
                className="p-3 bg-surface rounded-lg flex items-center gap-3 border border-border"
                data-testid="clause-document-freshness-row"
              >
                <div className="p-1.5 rounded bg-primary/15 flex-shrink-0" aria-hidden="true">
                  <FileText className="w-3 h-3 text-primary" />
                </div>
                <div className="flex-grow min-w-0">
                  <p className="text-sm text-foreground truncate">
                    {doc.title ??
                      (doc.document_id != null
                        ? `Document ${doc.document_id}`
                        : 'Unresolved document')}
                  </p>
                  <p className="text-xs text-muted-foreground">{tipNote}</p>
                </div>
                <Badge
                  variant={clauseDocumentFreshnessTone(doc.freshness)}
                  data-testid="clause-document-freshness-badge"
                >
                  {clauseDocumentFreshnessLabel(doc.freshness)}
                </Badge>
                {href ? (
                  <Link
                    to={href}
                    className="p-1 rounded text-primary hover:text-primary/80 hover:bg-primary/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    aria-label={`Open Standards & Evidence for document ${doc.document_id}`}
                    data-testid="clause-document-evidence-link"
                  >
                    <ArrowUpRight className="w-4 h-4" aria-hidden="true" />
                  </Link>
                ) : null}
              </div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
