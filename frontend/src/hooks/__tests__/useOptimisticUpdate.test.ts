import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useOptimisticUpdate } from '../useOptimisticUpdate'

describe('useOptimisticUpdate', () => {
  it('applies optimistic data then commits server result', async () => {
    const { result } = renderHook(() => useOptimisticUpdate({ count: 0 }))
    expect(result.current.data).toEqual({ count: 0 })

    await act(async () => {
      await result.current.optimisticUpdate({ count: 1 }, async () => ({ count: 2 }))
    })

    expect(result.current.data).toEqual({ count: 2 })
    expect(result.current.isPending).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('rolls back on failure and surfaces error message', async () => {
    const { result } = renderHook(() => useOptimisticUpdate({ count: 0 }))

    await act(async () => {
      await expect(
        result.current.optimisticUpdate({ count: 9 }, async () => {
          throw new Error('nope')
        }),
      ).rejects.toThrow('nope')
    })

    expect(result.current.data).toEqual({ count: 0 })
    expect(result.current.error).toBe('nope')
    expect(result.current.isPending).toBe(false)
  })

  it('uses explicit rollback data when provided', async () => {
    const { result } = renderHook(() => useOptimisticUpdate({ count: 1 }))

    await act(async () => {
      await expect(
        result.current.optimisticUpdate(
          { count: 99 },
          async () => {
            throw 'fail'
          },
          { count: 5 },
        ),
      ).rejects.toBe('fail')
    })

    expect(result.current.data).toEqual({ count: 5 })
    expect(result.current.error).toBe('Update failed')
  })
})
