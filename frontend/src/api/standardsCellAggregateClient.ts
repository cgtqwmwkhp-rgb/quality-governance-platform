/**
 * Standards cell aggregate API client (Wave 1 PR-B).
 * Extracted so ComplianceEvidence.tsx stays thin.
 */
import type { AxiosInstance } from 'axios'
import type {
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
  }
}
