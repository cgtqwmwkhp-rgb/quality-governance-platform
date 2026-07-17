import { knowledgeExceptionsClosedLoopHref } from '../helpers/knowledgeExceptionsLinks'

export type DocumentDownstreamPhase = 'processing' | 'indexed' | 'failed' | 'other'

export interface DocumentDownstreamView {
  phase: DocumentDownstreamPhase
  titleKey: string
  descriptionKey: string
  showExceptionsLink: boolean
  showDocumentControlNote: boolean
}

export function resolveDocumentDownstreamPhase(status: string): DocumentDownstreamPhase {
  if (status === 'processing') return 'processing'
  if (status === 'indexed') return 'indexed'
  if (status === 'failed') return 'failed'
  return 'other'
}

export function buildDocumentDownstreamView(doc: {
  id: number
  status: string
  indexed_at?: string
}): DocumentDownstreamView {
  const phase = resolveDocumentDownstreamPhase(doc.status)
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
