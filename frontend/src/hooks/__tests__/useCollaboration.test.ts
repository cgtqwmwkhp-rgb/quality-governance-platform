import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:8000',
}))

import useCollaboration from '../useCollaboration'

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
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close', { code: 1000, reason: '', wasClean: true }))
  })

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  simulateMessage(data: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) }))
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close', { code: 1000, reason: '', wasClean: true }))
  }
}

const defaultOptions = {
  documentId: 'doc-123',
  userId: 'user-1',
  userName: 'Alice',
  userColor: '#10B981',
}

describe('useCollaboration', () => {
  const OriginalWebSocket = globalThis.WebSocket

  beforeEach(() => {
    vi.clearAllMocks()
    MockWebSocket.instances = []
    // @ts-expect-error mock WebSocket constructor
    globalThis.WebSocket = MockWebSocket
  })

  afterEach(() => {
    globalThis.WebSocket = OriginalWebSocket
  })

  it('auto-connects on mount and targets the collab WebSocket endpoint', () => {
    renderHook(() => useCollaboration(defaultOptions))

    expect(MockWebSocket.instances).toHaveLength(1)
    const url = new URL(MockWebSocket.instances[0].url)
    expect(url.pathname).toBe('/api/v1/realtime/collab/doc-123')
    expect(url.searchParams.get('userId')).toBe('user-1')
    expect(url.protocol).toMatch(/^ws/)
  })

  it('does not auto-connect when autoConnect is false', () => {
    renderHook(() => useCollaboration({ ...defaultOptions, autoConnect: false }))

    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('marks connected, sends awareness, and exposes local user on open', () => {
    const { result } = renderHook(() => useCollaboration(defaultOptions))
    const ws = MockWebSocket.instances[0]

    act(() => {
      ws.simulateOpen()
    })

    expect(result.current.state.isConnected).toBe(true)
    expect(result.current.state.localUser).toEqual(
      expect.objectContaining({ id: 'user-1', name: 'Alice', color: '#10B981' }),
    )
    expect(ws.send).toHaveBeenCalledTimes(1)
    const awarenessPayload = JSON.parse(ws.send.mock.calls[0][0] as string)
    expect(awarenessPayload).toEqual({
      type: 'awareness',
      user: expect.objectContaining({ id: 'user-1', name: 'Alice', color: '#10B981' }),
    })
  })

  it('handles sync messages and invokes onSync', () => {
    const onSync = vi.fn()
    const { result } = renderHook(() =>
      useCollaboration({ ...defaultOptions, onSync }),
    )
    const ws = MockWebSocket.instances[0]

    act(() => {
      ws.simulateOpen()
      ws.simulateMessage({ type: 'sync' })
    })

    expect(result.current.state.isSynced).toBe(true)
    expect(onSync).toHaveBeenCalledTimes(1)
  })

  it('handles remote update messages and invokes onUpdate', () => {
    const onUpdate = vi.fn()
    const { result } = renderHook(() =>
      useCollaboration({ ...defaultOptions, onUpdate }),
    )
    const ws = MockWebSocket.instances[0]

    act(() => {
      ws.simulateOpen()
      ws.simulateMessage({ type: 'update', update: [1, 2, 3] })
    })

    expect(onUpdate).toHaveBeenCalledWith(new Uint8Array([1, 2, 3]))
    expect(result.current.state.isConnected).toBe(true)
  })

  it('tracks collaborators from awareness messages excluding the local user', () => {
    const { result } = renderHook(() => useCollaboration(defaultOptions))
    const ws = MockWebSocket.instances[0]

    act(() => {
      ws.simulateOpen()
      ws.simulateMessage({
        type: 'awareness',
        users: [
          { id: 'user-1', name: 'Alice', color: '#10B981', lastActive: '2026-07-13T00:00:00Z' },
          { id: 'user-2', name: 'Bob', color: '#3B82F6', lastActive: '2026-07-13T01:00:00Z' },
        ],
      })
    })

    expect(result.current.state.collaborators).toHaveLength(1)
    expect(result.current.state.collaborators[0]).toEqual(
      expect.objectContaining({ id: 'user-2', name: 'Bob' }),
    )
  })

  it('broadcasts local updates and manages undo/redo stacks', () => {
    const { result } = renderHook(() => useCollaboration(defaultOptions))
    const ws = MockWebSocket.instances[0]

    act(() => {
      ws.simulateOpen()
    })

    const update = new Uint8Array([9, 8, 7])

    act(() => {
      result.current.applyUpdate(update)
    })

    expect(ws.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'update', update: [9, 8, 7] }),
    )
    expect(result.current.canUndo).toBe(true)
    expect(result.current.canRedo).toBe(false)

    act(() => {
      result.current.undo()
    })

    expect(result.current.canUndo).toBe(false)
    expect(result.current.canRedo).toBe(true)

    act(() => {
      result.current.redo()
    })

    expect(result.current.canUndo).toBe(true)
    expect(result.current.canRedo).toBe(false)
  })

  it('sends cursor updates when the socket is open', () => {
    const { result } = renderHook(() => useCollaboration(defaultOptions))
    const ws = MockWebSocket.instances[0]

    act(() => {
      ws.simulateOpen()
      result.current.updateCursor(5, 2)
    })

    expect(ws.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'cursor', cursor: { index: 5, length: 2 } }),
    )
  })

  it('disconnect clears connection state on close', () => {
    const { result } = renderHook(() => useCollaboration(defaultOptions))
    const ws = MockWebSocket.instances[0]

    act(() => {
      ws.simulateOpen()
    })
    expect(result.current.state.isConnected).toBe(true)

    act(() => {
      result.current.disconnect()
    })

    expect(ws.close).toHaveBeenCalled()
    expect(result.current.state.isConnected).toBe(false)
    expect(result.current.state.isSynced).toBe(false)
  })
})
