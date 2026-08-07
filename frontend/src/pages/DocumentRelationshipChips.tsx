import { Link } from 'react-router-dom'
import { AlertTriangle, Link2, ShieldCheck } from 'lucide-react'
import { Badge } from '../components/ui/Badge'
import { documentRelationshipsHref } from './documentEvidenceTab'
import type { DocumentRelationshipSummary } from './documentRelationshipHelpers'

export interface DocumentRelationshipChipsProps {
  documentId: number
  summary: DocumentRelationshipSummary
  /** Confirmed clause evidence links, so governance depth is legible without opening a tab. */
  evidenceCount: number
}

/**
 * Ambient governance counts shown beside the document header on every tab.
 *
 * These are Doc Graph relationships and clause evidence, not the Golden Thread —
 * that stays the controlled document's library link.
 */
export function DocumentRelationshipChips({
  documentId,
  summary,
  evidenceCount,
}: DocumentRelationshipChipsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="document-relationship-chips">
      <Link
        to={documentRelationshipsHref(documentId)}
        className="inline-flex"
        data-testid="document-relationship-chip-total"
      >
        <Badge variant="outline" className="cursor-pointer">
          <Link2 className="mr-1 h-3 w-3" />
          {summary.confirmed} relationship{summary.confirmed === 1 ? '' : 's'}
        </Badge>
      </Link>
      {summary.pending > 0 ? (
        <Link
          to={documentRelationshipsHref(documentId)}
          className="inline-flex"
          data-testid="document-relationship-chip-pending"
        >
          <Badge variant="warning" className="cursor-pointer">
            {summary.pending} to confirm
          </Badge>
        </Link>
      ) : null}
      {summary.conflicts > 0 ? (
        <Link
          to={documentRelationshipsHref(documentId)}
          className="inline-flex"
          data-testid="document-relationship-chip-conflicts"
        >
          <Badge variant="destructive" className="cursor-pointer">
            <AlertTriangle className="mr-1 h-3 w-3" />
            {summary.conflicts} conflict{summary.conflicts === 1 ? '' : 's'}
          </Badge>
        </Link>
      ) : null}
      <Badge variant="outline" data-testid="document-relationship-chip-evidence">
        <ShieldCheck className="mr-1 h-3 w-3" />
        {evidenceCount} clause evidence
      </Badge>
    </div>
  )
}

export default DocumentRelationshipChips
