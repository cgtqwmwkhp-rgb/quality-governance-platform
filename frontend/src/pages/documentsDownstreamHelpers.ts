import { knowledgeExceptionsClosedLoopHref } from '../helpers/knowledgeExceptionsLinks'

export type DocumentDownstreamPhase = 'processing' | 'indexed' | 'failed' | 'other'

export interface DocumentDownstreamView {
  phase: DocumentDownstreamPhase
  titleKey: string
  descriptionKey: string
  showExceptionsLink: boolean
  showDocumentControlNote: boolean
}

export function resolveDocumentDownstreamPhase(
  status: string,
  indexedAt?: string | null,
  chunkCount?: number | null,
  hasAiSummary?: boolean,
): DocumentDownstreamPhase {
  if (status === 'processing') return 'processing'
  if (status === 'failed') return 'failed'
  // Publish overwrites status to `published` but must not hide successful content indexing.
  if (
    status === 'indexed' ||
    Boolean(indexedAt) ||
    (typeof chunkCount === 'number' && chunkCount > 0) ||
    Boolean(hasAiSummary)
  ) {
    return 'indexed'
  }
  return 'other'
}

export function buildDocumentDownstreamView(doc: {
  id: number
  status: string
  indexed_at?: string | null
  chunk_count?: number | null
  ai_summary?: string | null
}): DocumentDownstreamView {
  const phase = resolveDocumentDownstreamPhase(
    doc.status,
    doc.indexed_at,
    doc.chunk_count,
    Boolean(doc.ai_summary && doc.ai_summary.trim()),
  )
  switch (phase) {
    case 'processing':
      return {
        phase,
        titleKey: 'documents.downstream.processing.title',
        descriptionKey: 'documents.downstream.processing.description',
        showExceptionsLink: false,
        showDocumentControlNote: false,
      }
    case 'indexed':
      return {
        phase,
        titleKey: 'documents.downstream.indexed.title',
        descriptionKey: 'documents.downstream.indexed.description',
        showExceptionsLink: true,
        showDocumentControlNote: true,
      }
    case 'failed':
      return {
        phase,
        titleKey: 'documents.downstream.failed.title',
        descriptionKey: 'documents.downstream.failed.description',
        showExceptionsLink: false,
        showDocumentControlNote: false,
      }
    default:
      return {
        phase,
        titleKey: 'documents.downstream.other.title',
        descriptionKey: 'documents.downstream.other.description',
        showExceptionsLink: false,
        showDocumentControlNote: false,
      }
  }
}

export function buildDocumentsExceptionsHref(documentId: number): string {
  return knowledgeExceptionsClosedLoopHref('document', documentId)
}

export const DOCUMENT_CONTROL_GOLDEN_THREAD_PATH = '/document-control'
