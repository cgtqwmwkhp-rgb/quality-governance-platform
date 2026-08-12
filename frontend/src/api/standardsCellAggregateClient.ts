/**
 * Standards cell aggregate API client (Wave 1 PR-B).
 * Extracted so ComplianceEvidence.tsx stays thin.
 */
import type { AxiosInstance } from 'axios'
import type {
  AlignmentCatalogueResponse,
  ExactShareApplyResponse,
  ExactShareUndoResponse,
  StandardsCellAggregate,
  StandardsCellMatrixSummary,
} from './standardsCellAggregateTypes'

export function createStandardsCellAggregateApi(api: AxiosInstance) {
  return {
    getCell: (framework: string, clause: string) => {
      const sp = new URLSearchParams()
      sp.set('framework', framework)
      sp.set('clause', clause)
      return api.get<StandardsCellAggregate>(`/api/v1/compliance/cell-aggregate?${sp}`)
    },
    getMatrix: (frameworks: string[], clauses: string[]) => {
      const sp = new URLSearchParams()
      sp.set('frameworks', frameworks.join(','))
      sp.set('clauses', clauses.join(','))
      return api.get<StandardsCellMatrixSummary>(`/api/v1/compliance/cell-aggregate/matrix?${sp}`)
    },
    /**
     * Imported PEL-HSEQ-5064 clause axis (Wave 2 PR-C).
     * Returns `matrix_loaded: false` with no rows when nothing has been imported —
     * callers must fall back to their own axis and say so.
     */
    getAlignmentCatalogue: (params?: { framework?: string; verdict?: string }) => {
      const sp = new URLSearchParams()
      if (params?.framework) sp.set('framework', params.framework)
      if (params?.verdict) sp.set('verdict', params.verdict)
      const query = sp.toString()
      return api.get<AlignmentCatalogueResponse>(
        `/api/v1/compliance/alignment/catalogue${query ? `?${query}` : ''}`,
      )
    },
    /** Wave 2 PR-D: create-only share onto EXACT peer columns. */
    applyExactShare: (body: {
      source_link_id: number
      source_framework: string
      source_clause: string
      target_frameworks: string[]
      matrix_version_id: number
    }) => api.post<ExactShareApplyResponse>('/api/v1/compliance/evidence/exact-share', body),
    /** Wave 2 PR-D: soft-delete links created by a prior apply. */
    undoExactShare: (body: { link_ids: number[]; applied_at: string }) =>
      api.post<ExactShareUndoResponse>('/api/v1/compliance/evidence/exact-share/undo', body),
  }
}
