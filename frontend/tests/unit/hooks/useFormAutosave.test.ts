import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFormAutosave } from '../../../src/hooks/useFormAutosave';

vi.mock('../../../src/services/telemetry', () => ({
  trackExp001DraftSaved: vi.fn(),
  trackExp001DraftRecovered: vi.fn(),
  trackExp001DraftDiscarded: vi.fn(),
}));

interface TestFormData extends Record<string, unknown> {
  name: string;
  email: string;
}

describe('useFormAutosave', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('initializes with no draft', () => {
    const { result } = renderHook(() =>
      useFormAutosave<TestFormData>({ formType: 'test_form' })
    );

    expect(result.current.hasDraft).toBe(false);
    expect(result.current.draftData).toBeNull();
    expect(result.current.lastSavedAt).toBeNull();
  });

  it('saves a draft immediately with saveNow', () => {
    const { result } = renderHook(() =>
      useFormAutosave<TestFormData>({ formType: 'test_form' })
    );

    act(() => {
      result.current.saveNow({ name: 'John', email: 'john@test.com' }, 1);
    });

    expect(result.current.hasDraft).toBe(true);
    expect(result.current.lastSavedAt).not.toBeNull();
    expect(localStorage.getItem('portal_form_draft_test_form')).not.toBeNull();
  });

  it('saves a draft with debounce via saveDraft', () => {
    const { result } = renderHook(() =>
      useFormAutosave<TestFormData>({ formType: 'debounce_form' })
    );

    act(() => {
      result.current.saveDraft({ name: 'Jane', email: 'jane@test.com' }, 0);
    });

    expect(result.current.hasDraft).toBe(false);

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(result.current.hasDraft).toBe(true);
  });

  it('discards a draft', () => {
    const { result } = renderHook(() =>
      useFormAutosave<TestFormData>({ formType: 'discard_form' })
    );

    act(() => {
      result.current.saveNow({ name: 'Test', email: 'test@test.com' }, 0);
    });

    expect(result.current.hasDraft).toBe(true);

    act(() => {
      result.current.discardDraft();
    });

    expect(result.current.hasDraft).toBe(false);
    expect(localStorage.getItem('portal_form_draft_discard_form')).toBeNull();
  });

  it('recovers draft data', () => {
    const draftPayload = {
      formType: 'recover_form',
      data: { name: 'Recovery', email: 'recover@test.com' },
      step: 2,
      savedAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 86400000).toISOString(),
      version: '1.0',
    };
    localStorage.setItem('portal_form_draft_recover_form', JSON.stringify(draftPayload));

    const { result } = renderHook(() =>
      useFormAutosave<TestFormData>({ formType: 'recover_form' })
    );

    expect(result.current.hasDraft).toBe(true);

    let recovered: TestFormData | null = null;
    act(() => {
      recovered = result.current.recoverDraft();
    });

    expect(recovered).toEqual({ name: 'Recovery', email: 'recover@test.com' });
  });

  it('does not save when disabled', () => {
    const { result } = renderHook(() =>
      useFormAutosave<TestFormData>({ formType: 'disabled_form', enabled: false })
    );

    act(() => {
      result.current.saveNow({ name: 'No', email: 'no@test.com' }, 0);
    });

    expect(result.current.hasDraft).toBe(false);
  });
});
