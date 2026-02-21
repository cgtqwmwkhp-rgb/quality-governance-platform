import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFeatureFlag, setFeatureFlagOverride, clearFeatureFlagOverride } from '../../../src/hooks/useFeatureFlag';

describe('useFeatureFlag', () => {
  beforeEach(() => {
    localStorage.clear();
    delete (window as Record<string, unknown>).__FEATURE_FLAGS__;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns false for unknown flag names', () => {
    const { result } = renderHook(() => useFeatureFlag('nonexistent_flag'));
    expect(result.current).toBe(false);
  });

  it('returns the default value for a known flag', () => {
    const { result } = renderHook(() => useFeatureFlag('portal_form_autosave'));
    expect(result.current).toBe(false);
  });

  it('returns true when runtime flag is set', () => {
    (window as Record<string, unknown>).__FEATURE_FLAGS__ = { admin_ai_copilot: true };
    const { result } = renderHook(() => useFeatureFlag('admin_ai_copilot'));
    expect(result.current).toBe(true);
  });

  it('localStorage override takes priority over runtime flags', () => {
    (window as Record<string, unknown>).__FEATURE_FLAGS__ = { admin_ai_copilot: false };
    localStorage.setItem('ff_override_admin_ai_copilot', 'true');
    const { result } = renderHook(() => useFeatureFlag('admin_ai_copilot'));
    expect(result.current).toBe(true);
  });

  it('responds to storage events for cross-tab sync', () => {
    const { result } = renderHook(() => useFeatureFlag('portal_form_autosave'));
    expect(result.current).toBe(false);

    act(() => {
      localStorage.setItem('ff_override_portal_form_autosave', 'true');
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: 'ff_override_portal_form_autosave',
          newValue: 'true',
        })
      );
    });

    expect(result.current).toBe(true);
  });
});

describe('setFeatureFlagOverride', () => {
  beforeEach(() => localStorage.clear());

  it('sets a localStorage override', () => {
    setFeatureFlagOverride('portal_form_autosave', true);
    expect(localStorage.getItem('ff_override_portal_form_autosave')).toBe('true');
  });

  it('can set override to false', () => {
    setFeatureFlagOverride('portal_form_autosave', false);
    expect(localStorage.getItem('ff_override_portal_form_autosave')).toBe('false');
  });
});

describe('clearFeatureFlagOverride', () => {
  beforeEach(() => localStorage.clear());

  it('removes the localStorage override', () => {
    localStorage.setItem('ff_override_portal_form_autosave', 'true');
    clearFeatureFlagOverride('portal_form_autosave');
    expect(localStorage.getItem('ff_override_portal_form_autosave')).toBeNull();
  });
});
