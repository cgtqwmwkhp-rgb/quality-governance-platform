import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import {
  clearFeatureFlagOverride,
  setFeatureFlagOverride,
  useFeatureFlag,
} from '../useFeatureFlag'

describe('useFeatureFlag', () => {
  afterEach(() => {
    clearFeatureFlagOverride('portal_form_autosave')
    clearFeatureFlagOverride('admin_user_management')
    delete window.__FEATURE_FLAGS__
  })

  it('returns defaults and honors localStorage overrides', () => {
    const { result, unmount } = renderHook(() => useFeatureFlag('portal_form_autosave'))
    expect(result.current).toBe(false)
    unmount()

    setFeatureFlagOverride('portal_form_autosave', true)
    const { result: enabled } = renderHook(() => useFeatureFlag('portal_form_autosave'))
    expect(enabled.current).toBe(true)
  })

  it('prefers runtime window flags when no override is set', () => {
    window.__FEATURE_FLAGS__ = { advanced_analytics: true }
    const { result } = renderHook(() => useFeatureFlag('advanced_analytics'))
    expect(result.current).toBe(true)
  })

  it('unknown flags default to false', () => {
    const { result } = renderHook(() => useFeatureFlag('not_a_real_flag'))
    expect(result.current).toBe(false)
  })

  it('reacts to storage events for the same override key', async () => {
    const { result } = renderHook(() => useFeatureFlag('portal_form_autosave'))
    expect(result.current).toBe(false)

    act(() => {
      localStorage.setItem('ff_override_portal_form_autosave', 'true')
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: 'ff_override_portal_form_autosave',
          newValue: 'true',
        }),
      )
    })

    await waitFor(() => {
      expect(result.current).toBe(true)
    })
  })
})
