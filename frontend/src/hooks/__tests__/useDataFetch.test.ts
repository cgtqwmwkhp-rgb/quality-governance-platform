import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useDataFetch } from '../useDataFetch'

describe('useDataFetch', () => {
  it('loads data on mount and supports refetch', async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce({ id: 1 })
      .mockResolvedValueOnce({ id: 2 })

    const { result } = renderHook(() => useDataFetch(fetchFn, []))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.data).toEqual({ id: 1 })
    expect(result.current.error).toBeNull()

    await act(async () => {
      await result.current.refetch()
    })
    expect(result.current.data).toEqual({ id: 2 })
    expect(fetchFn).toHaveBeenCalledTimes(2)
  })

  it('captures errors as messages', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useDataFetch(fetchFn, []))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.data).toBeNull()
    expect(result.current.error).toBe('boom')
  })

  it('uses generic message for non-Error rejections', async () => {
    const fetchFn = vi.fn().mockRejectedValue('x')
    const { result } = renderHook(() => useDataFetch(fetchFn, []))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.error).toBe('An error occurred')
  })
})
