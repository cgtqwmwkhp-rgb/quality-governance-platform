import { useState, useCallback } from 'react'

interface OptimisticState<T> {
  data: T
  isPending: boolean
  error: string | null
}

export function useOptimisticUpdate<T>(initialData: T) {
  const [state, setState] = useState<OptimisticState<T>>({
    data: initialData,
    isPending: false,
    error: null,
  })

  const optimisticUpdate = useCallback(
    async (optimisticData: T, serverFn: () => Promise<T>, rollbackData?: T) => {
      const previousData = state.data
      setState({ data: optimisticData, isPending: true, error: null })

      try {
        const result = await serverFn()
        setState({ data: result, isPending: false, error: null })
        return result
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Update failed'
        setState({
          data: rollbackData ?? previousData,
          isPending: false,
          error: errorMessage,
        })
        throw err
      }
    },
    [state.data],
  )

  return { ...state, optimisticUpdate }
}
