import type { StandardsCellAggregate } from '../../../api/standardsCellAggregateTypes'

export type CellAggregateViewProps = {
  data: StandardsCellAggregate | null
  loading: boolean
  error: string | null
  clauseNumber?: string | null
  frameworkId?: string | null
}
