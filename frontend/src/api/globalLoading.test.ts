import { describe, expect, it, vi } from 'vitest'
import {
  beginGlobalLoading,
  endGlobalLoading,
  shouldTrackGlobalLoading,
} from './globalLoading'

describe('globalLoading', () => {
  it('does not track by default (no global flash)', () => {
    expect(shouldTrackGlobalLoading(undefined)).toBe(false)
    expect(shouldTrackGlobalLoading({})).toBe(false)
    expect(shouldTrackGlobalLoading({ globalLoading: false })).toBe(false)
  })

  it('tracks only when globalLoading is explicitly true', () => {
    expect(shouldTrackGlobalLoading({ globalLoading: true })).toBe(true)
  })

  it('scopes setLoading to opted-in requests only', () => {
    const setLoading = vi.fn()
    let active = 0

    active = beginGlobalLoading(active, false, setLoading)
    expect(active).toBe(0)
    expect(setLoading).not.toHaveBeenCalled()

    active = beginGlobalLoading(active, true, setLoading)
    expect(active).toBe(1)
    expect(setLoading).toHaveBeenCalledWith(true)

    active = beginGlobalLoading(active, true, setLoading)
    expect(active).toBe(2)
    expect(setLoading).toHaveBeenCalledTimes(1)

    active = endGlobalLoading(active, true, setLoading)
    expect(active).toBe(1)
    expect(setLoading).toHaveBeenCalledTimes(1)

    active = endGlobalLoading(active, false, setLoading)
    expect(active).toBe(1)

    active = endGlobalLoading(active, true, setLoading)
    expect(active).toBe(0)
    expect(setLoading).toHaveBeenLastCalledWith(false)
  })
})
