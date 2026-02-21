import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import useWebSocket from '../../../src/hooks/useWebSocket';

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static CONNECTING = 0;

  url: string;
  readyState = MockWebSocket.CONNECTING;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
  }

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: 1000 }));
    }
  });

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  simulateMessage(data: Record<string, unknown>) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }
}

describe('useWebSocket', () => {
  let mockWsInstance: MockWebSocket | null = null;

  beforeEach(() => {
    mockWsInstance = null;
    vi.stubGlobal('WebSocket', class extends MockWebSocket {
      constructor(url: string) {
        super(url);
        mockWsInstance = this;
      }
    });
    (globalThis.WebSocket as unknown as Record<string, number>).OPEN = MockWebSocket.OPEN;
    (globalThis.WebSocket as unknown as Record<string, number>).CLOSED = MockWebSocket.CLOSED;
    (globalThis.WebSocket as unknown as Record<string, number>).CONNECTING = MockWebSocket.CONNECTING;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with disconnected state when autoConnect is false', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: false })
    );

    expect(result.current.isConnected).toBe(false);
    expect(result.current.isConnecting).toBe(false);
    expect(result.current.lastMessage).toBeNull();
    expect(result.current.notifications).toEqual([]);
    expect(result.current.unreadCount).toBe(0);
  });

  it('exposes expected API methods', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: false })
    );

    expect(typeof result.current.connect).toBe('function');
    expect(typeof result.current.disconnect).toBe('function');
    expect(typeof result.current.subscribe).toBe('function');
    expect(typeof result.current.unsubscribe).toBe('function');
    expect(typeof result.current.send).toBe('function');
    expect(typeof result.current.clearNotifications).toBe('function');
    expect(typeof result.current.markAsRead).toBe('function');
  });

  it('sets isConnecting to true when connect is called', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: false })
    );

    act(() => {
      result.current.connect();
    });

    expect(result.current.isConnecting).toBe(true);
  });

  it('sets isConnected to true when WebSocket opens', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: false })
    );

    act(() => {
      result.current.connect();
    });

    act(() => {
      mockWsInstance!.simulateOpen();
    });

    expect(result.current.isConnected).toBe(true);
    expect(result.current.isConnecting).toBe(false);
  });

  it('processes incoming messages and updates lastMessage', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: false })
    );

    act(() => {
      result.current.connect();
    });

    act(() => {
      mockWsInstance!.simulateOpen();
    });

    act(() => {
      mockWsInstance!.simulateMessage({ type: 'pong' });
    });

    expect(result.current.lastMessage).toEqual({ type: 'pong' });
  });

  it('clears notifications via clearNotifications()', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: false })
    );

    act(() => {
      result.current.clearNotifications();
    });

    expect(result.current.notifications).toEqual([]);
    expect(result.current.unreadCount).toBe(0);
  });

  it('marks a notification as read', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: false })
    );

    act(() => {
      result.current.connect();
    });

    act(() => {
      mockWsInstance!.simulateOpen();
    });

    act(() => {
      mockWsInstance!.simulateMessage({
        type: 'notification',
        data: {
          id: 42,
          type: 'info',
          priority: 'normal',
          title: 'Test',
          message: 'Hello',
          is_read: false,
          created_at: new Date().toISOString(),
        },
      });
    });

    expect(result.current.unreadCount).toBe(1);

    act(() => {
      result.current.markAsRead(42);
    });

    expect(result.current.unreadCount).toBe(0);
    expect(result.current.notifications[0].is_read).toBe(true);
  });
});
