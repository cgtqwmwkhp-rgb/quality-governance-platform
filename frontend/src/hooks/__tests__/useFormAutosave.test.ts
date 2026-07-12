import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as telemetry from '../../services/telemetry'
import { useFormAutosave } from '../useFormAutosave'

type DraftShape = { name: string; note?: string }

const FORM_TYPE = 'incident_report'
const STORAGE_KEY = `portal_form_draft_${FORM_TYPE}`

function makeStoredDraft(overrides: Record<string, unknown> = {}) {
  const now = Date.now()
  return {
    formType: FORM_TYPE,
    data: { name: 'Ada' } satisfies DraftShape,
    step: 1,
    savedAt: new Date(now - 60_000).toISOString(),
    expiresAt: new Date(now + 60 * 60 * 1000).toISOString(),
    version: '1.0',
    ...overrides,
  }
}

describe('useFormAutosave', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    vi.clearAllMocks()
    vi.spyOn(telemetry, 'trackExp001DraftSaved')
    vi.spyOn(telemetry, 'trackExp001DraftRecovered')
    vi.spyOn(telemetry, 'trackExp001DraftDiscarded')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true } as Response),
    )
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    localStorage.clear()
    sessionStorage.clear()
  })

  it('starts empty when no draft is stored', () => {
    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    expect(result.current.hasDraft).toBe(false)
    expect(result.current.draftData).toBeNull()
    expect(result.current.isRecoveryPromptOpen).toBe(false)
    expect(result.current.lastSavedAt).toBeNull()
  })

  it('loads a valid draft and opens the recovery prompt', async () => {
    const onDraftFound = vi.fn()
    const stored = makeStoredDraft()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))

    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE, onDraftFound }),
    )

    await waitFor(() => {
      expect(result.current.hasDraft).toBe(true)
    })
    expect(result.current.draftData?.data).toEqual({ name: 'Ada' })
    expect(result.current.isRecoveryPromptOpen).toBe(true)
    expect(onDraftFound).toHaveBeenCalledWith(
      expect.objectContaining({ formType: FORM_TYPE, step: 1 }),
    )
  })

  it('discards drafts with incompatible schema versions', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(makeStoredDraft({ version: '0.9' })),
    )

    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    })
    expect(result.current.hasDraft).toBe(false)
  })

  it('discards expired drafts on load', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(
        makeStoredDraft({
          expiresAt: new Date(Date.now() - 1000).toISOString(),
        }),
      ),
    )

    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    })
    expect(result.current.hasDraft).toBe(false)
  })

  it('ignores corrupt stored JSON without throwing', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    localStorage.setItem(STORAGE_KEY, '{not-json')

    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    await waitFor(() => {
      expect(warn).toHaveBeenCalled()
    })
    expect(result.current.hasDraft).toBe(false)
    warn.mockRestore()
  })

  it('saveNow persists draft and emits telemetry', () => {
    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    act(() => {
      result.current.saveNow({ name: 'Grace' }, 2)
    })

    expect(result.current.hasDraft).toBe(true)
    expect(result.current.draftData?.data).toEqual({ name: 'Grace' })
    expect(result.current.lastSavedAt).toBeInstanceOf(Date)
    expect(telemetry.trackExp001DraftSaved).toHaveBeenCalledWith(FORM_TYPE, 2)

    const raw = localStorage.getItem(STORAGE_KEY)
    expect(raw).toBeTruthy()
    expect(JSON.parse(raw!).data).toEqual({ name: 'Grace' })
  })

  it('saveDraft debounces before calling saveNow', () => {
    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    act(() => {
      result.current.saveDraft({ name: 'first' }, 1)
      result.current.saveDraft({ name: 'second' }, 1)
    })

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()

    act(() => {
      vi.advanceTimersByTime(500)
    })

    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).data).toEqual({
      name: 'second',
    })
    expect(telemetry.trackExp001DraftSaved).toHaveBeenCalledTimes(1)
  })

  it('recoverDraft returns data, closes prompt, and tracks recovery', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeStoredDraft()))

    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    await waitFor(() => {
      expect(result.current.hasDraft).toBe(true)
    })

    let recovered: DraftShape | null = null
    act(() => {
      recovered = result.current.recoverDraft()
    })

    expect(recovered).toEqual({ name: 'Ada' })
    expect(result.current.isRecoveryPromptOpen).toBe(false)
    expect(telemetry.trackExp001DraftRecovered).toHaveBeenCalledWith(
      FORM_TYPE,
      expect.any(Number),
    )
  })

  it('recoverDraft returns null when no draft is loaded', () => {
    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    let recovered: DraftShape | null = { name: 'x' }
    act(() => {
      recovered = result.current.recoverDraft()
    })
    expect(recovered).toBeNull()
    expect(telemetry.trackExp001DraftRecovered).not.toHaveBeenCalled()
  })

  it('discardDraft clears storage and tracks discard', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeStoredDraft()))

    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    await waitFor(() => {
      expect(result.current.hasDraft).toBe(true)
    })

    act(() => {
      result.current.discardDraft()
    })

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    expect(result.current.hasDraft).toBe(false)
    expect(result.current.draftData).toBeNull()
    expect(result.current.isRecoveryPromptOpen).toBe(false)
    expect(telemetry.trackExp001DraftDiscarded).toHaveBeenCalledWith(
      FORM_TYPE,
      expect.any(Number),
    )
  })

  it('clearDraft delegates to discardDraft', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeStoredDraft()))

    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    await waitFor(() => {
      expect(result.current.hasDraft).toBe(true)
    })

    act(() => {
      result.current.clearDraft()
    })

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    expect(result.current.hasDraft).toBe(false)
  })

  it('openRecoveryPrompt only opens when a draft exists', () => {
    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    act(() => {
      result.current.openRecoveryPrompt()
    })
    expect(result.current.isRecoveryPromptOpen).toBe(false)

    act(() => {
      result.current.saveNow({ name: 'Lin' }, 1)
      result.current.closeRecoveryPrompt()
    })
    expect(result.current.isRecoveryPromptOpen).toBe(false)

    act(() => {
      result.current.openRecoveryPrompt()
    })
    expect(result.current.isRecoveryPromptOpen).toBe(true)
  })

  it('is a no-op when disabled', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeStoredDraft()))

    const { result } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE, enabled: false }),
    )

    act(() => {
      result.current.saveNow({ name: 'nope' }, 1)
      result.current.saveDraft({ name: 'nope' }, 1)
    })

    act(() => {
      vi.advanceTimersByTime(500)
    })

    expect(result.current.hasDraft).toBe(false)
    expect(telemetry.trackExp001DraftSaved).not.toHaveBeenCalled()
  })

  it('clears pending debounce timer on unmount', () => {
    const { result, unmount } = renderHook(() =>
      useFormAutosave<DraftShape>({ formType: FORM_TYPE }),
    )

    act(() => {
      result.current.saveDraft({ name: 'pending' }, 1)
    })

    unmount()

    act(() => {
      vi.advanceTimersByTime(500)
    })

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
