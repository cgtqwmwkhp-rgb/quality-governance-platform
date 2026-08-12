import { useEffect, useState } from 'react'
import { standardsCellAggregateApi, getApiErrorMessage } from '../../api/client'
import type { StandardsCellAggregate } from '../../api/standardsCellAggregateTypes'
import type { FrameworkId } from '../standardsMatrixFilters'

export function useStandardsCellAggregate(
  frameworkId: FrameworkId | string | null | undefined,
  clauseNumber: string | null | undefined,
) {
  const [data, setData] = useState<StandardsCellAggregate | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const framework = (frameworkId || '').trim()
    const clause = (clauseNumber || '').trim()
    if (!framework || !clause) {
      setData(null)
      setError(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    standardsCellAggregateApi
      .getCell(framework, clause)
      .then((res) => {
        if (!cancelled) setData(res.data)
      })
      .catch((err) => {
        if (!cancelled) {
          setData(null)
          setError(getApiErrorMessage(err))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [frameworkId, clauseNumber])

  return { data, loading, error }
}
