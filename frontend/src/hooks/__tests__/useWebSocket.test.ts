import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'

const getPlatformToken = vi.fn()

vi.mock('../../utils/auth', () => ({
  getPlatformToken: (...args: unknown[]) => getPlatformToken(...args),
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:8000',
}))

import useWebSocket from '../useWebSocket'

type WsHandlers = {
  onopen: ((ev: Event) => void) | null
  onclose: ((ev: CloseEvent) => void) | null
  onerror: ((ev: Event) => void) | null
  onmessage: ((ev: MessageEvent) => void) | null
}

class MockWebSocket {
  static OPEN = 1
  static CONNECTING = 0
  static CLOSING = 2
  static CLOSED = 3
  static instances: MockWebSocket[] = []

  url: string
  readyState = MockWebSocket.CONNECTING
  onopen: WsHandlers['onopen'] = null
  onclose: WsHandlers['onclose'] = null
  onerror: WsHandlers['onerror'] = null
  onmessage: WsHandlers['onmessage'] = null
  send = vi.fn()
  close = vi.fn((code?: number, reason?: string) => {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(
      new CloseEvent('close', { code: code ?? 1000, reason: reason ?? '', wasClean: true }),
    )
  })

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  /** Simulate a successful open. */
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  /** Simulate a server close with the given code. */
  simulateClose(code: number, reason = '') {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close', { code, reason, wasClean: true }))
  }
}

describe('useWebSocket', () => {
  const OriginalWebSocket = globalThis.WebSocket

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    MockWebSocket.instances = []
    // @ts-expect-error mock WebSocket constructor
    globalThis.WebSocket = MockWebSocket
    getPlatformToken.mockReturnValue('test-jwt-token')
  })

  afterEach(() => {
    vi.useRealTimers()
    globalThis.WebSocket = OriginalWebSocket
  })

  it('includes getPlatformToken() as token query param on the WS URL', () => {
    renderHook(() => useWebSocket({ userId: 42, autoConnect: true, reconnectAttempts: 0 }))

    expect(MockWebSocket.instances).toHaveLength(1)
    const url = new URL(MockWebSocket.instances[0].url)
    expect(url.pathname).toBe('/api/v1/realtime/ws/42')
    expect(url.searchParams.get('token')).toBe('test-jwt-token')
    expect(url.protocol).toMatch(/^ws/)
  })

  it('does not connect when there is no access token', () => {
    getPlatformToken.mockReturnValue(null)

    const { result } = renderHook(() =>
      useWebSocket({ userId: 42, autoConnect: true, reconnectAttempts: 0 }),
    )

    expect(MockWebSocket.instances).toHaveLength(0)
    expect(result.current.isConnected).toBe(false)
    expect(result.current.isConnecting).toBe(false)

    act(() => {
      result.current.connect()
    })

    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('does not connect when userId is missing', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: true, reconnectAttempts: 0 }),
    )

    expect(MockWebSocket.instances).toHaveLength(0)

    act(() => {
      result.current.connect()
    })

    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('does not reconnect on auth close codes 4001 and 4003', () => {
    const { result } = renderHook(() =>
      useWebSocket({
        userId: 7,
        autoConnect: true,
        reconnectAttempts: 5,
        reconnectInterval: 1000,
      }),
    )

    expect(MockWebSocket.instances).toHaveLength(1)
    const first = MockWebSocket.instances[0]

    act(() => {
      first.simulateOpen()
    })
    expect(result.current.isConnected).toBe(true)

    act(() => {
      first.simulateClose(4001, 'Unauthorized')
    })
    expect(result.current.isConnected).toBe(false)

    act(() => {
      vi.advanceTimersByTime(60_000)
    })
    expect(MockWebSocket.instances).toHaveLength(1)

    // Manual reconnect after auth failure should still be possible if token exists,
    // but auto-reconnect must not have fired. Trigger a fresh connect and close 4003.
    act(() => {
      // Reset connecting gate: after auth close, isConnecting is false
      result.current.connect()
    })
    expect(MockWebSocket.instances).toHaveLength(2)

    act(() => {
      MockWebSocket.instances[1].simulateOpen()
      MockWebSocket.instances[1].simulateClose(4003, 'Forbidden')
    })

    act(() => {
      vi.advanceTimersByTime(60_000)
    })
    expect(MockWebSocket.instances).toHaveLength(2)
  })
})
