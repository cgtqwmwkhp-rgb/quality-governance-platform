import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useVoiceToText } from '../useVoiceToText'

class MockSpeechRecognition {
  continuous = false
  interimResults = false
  lang = ''
  onstart: ((event: Event) => void) | null = null
  onend: ((event: Event) => void) | null = null
  onerror: ((event: { error: string }) => void) | null = null
  onresult: ((event: { resultIndex: number; results: ArrayLike<unknown> }) => void) | null = null
  start = vi.fn()
  stop = vi.fn()
  abort = vi.fn()
}

describe('useVoiceToText', () => {
  let recognition: MockSpeechRecognition

  beforeEach(() => {
    recognition = new MockSpeechRecognition()
    vi.stubGlobal(
      'webkitSpeechRecognition',
      vi.fn(() => recognition),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('reports unsupported browsers without creating a recognition session', () => {
    vi.stubGlobal('webkitSpeechRecognition', undefined)

    const { result } = renderHook(() => useVoiceToText())

    expect(result.current.isSupported).toBe(false)
    expect(result.current.isListening).toBe(false)
  })

  it('configures browser recognition and starts a listening session', () => {
    const { result } = renderHook(() =>
      useVoiceToText({ continuous: true, language: 'cy-GB' }),
    )

    expect(result.current.isSupported).toBe(true)
    expect(recognition.continuous).toBe(true)
    expect(recognition.interimResults).toBe(true)
    expect(recognition.lang).toBe('cy-GB')

    act(() => {
      result.current.startListening()
      recognition.onstart?.(new Event('start'))
    })

    expect(recognition.start).toHaveBeenCalledOnce()
    expect(result.current.isListening).toBe(true)
  })

  it('publishes final speech and preserves interim speech for the operator', () => {
    const onResult = vi.fn()
    const { result } = renderHook(() => useVoiceToText({ onResult }))

    act(() => {
      recognition.onresult?.({
        resultIndex: 0,
        results: [
          { isFinal: false, 0: { transcript: 'draft note' } },
        ],
      })
    })

    expect(result.current.transcript).toBe('draft note')
    expect(onResult).not.toHaveBeenCalled()

    act(() => {
      recognition.onresult?.({
        resultIndex: 0,
        results: [
          { isFinal: true, 0: { transcript: 'final incident note' } },
        ],
      })
    })

    expect(result.current.transcript).toBe('final incident note')
    expect(onResult).toHaveBeenCalledWith('final incident note')
  })

  it('surfaces an actionable microphone-permission error and invokes the callback', () => {
    const onError = vi.fn()
    const { result } = renderHook(() => useVoiceToText({ onError }))

    act(() => {
      recognition.onstart?.(new Event('start'))
      recognition.onerror?.({ error: 'not-allowed' })
    })

    expect(result.current.isListening).toBe(false)
    expect(result.current.error).toBe(
      'Microphone access denied. Please allow microphone permissions.',
    )
    expect(onError).toHaveBeenCalledWith(
      'Microphone access denied. Please allow microphone permissions.',
    )
  })

  it('stops an active session and aborts it during unmount', () => {
    const { result, unmount } = renderHook(() => useVoiceToText())

    act(() => {
      recognition.onstart?.(new Event('start'))
    })

    act(() => {
      result.current.stopListening()
      recognition.onend?.(new Event('end'))
    })

    expect(recognition.stop).toHaveBeenCalledOnce()
    expect(result.current.isListening).toBe(false)

    unmount()

    expect(recognition.abort).toHaveBeenCalledOnce()
  })
})
