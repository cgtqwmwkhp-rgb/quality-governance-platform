import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

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
    if (this.onopen) this.onopen(new Event('open'));
  }
}

import useCollaboration from '../../../src/hooks/useCollaboration';

describe('useCollaboration', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', class extends MockWebSocket {
      constructor(url: string) {
        super(url);
      }
    });
    (globalThis.WebSocket as unknown as Record<string, number>).OPEN = MockWebSocket.OPEN;
    (globalThis.WebSocket as unknown as Record<string, number>).CLOSED = MockWebSocket.CLOSED;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with disconnected state', () => {
    const { result } = renderHook(() =>
      useCollaboration({
        documentId: 'doc-1',
        userId: 'user-1',
        userName: 'Test User',
        autoConnect: false,
      })
    );

    expect(result.current.state.isConnected).toBe(false);
    expect(result.current.state.isSynced).toBe(false);
    expect(result.current.state.collaborators).toEqual([]);
  });

  it('exposes connect and disconnect methods', () => {
    const { result } = renderHook(() =>
      useCollaboration({
        documentId: 'doc-1',
        userId: 'user-1',
        userName: 'Test User',
        autoConnect: false,
      })
    );

    expect(typeof result.current.connect).toBe('function');
    expect(typeof result.current.disconnect).toBe('function');
  });

  it('exposes undo and redo methods', () => {
    const { result } = renderHook(() =>
      useCollaboration({
        documentId: 'doc-1',
        userId: 'user-1',
        userName: 'Test User',
        autoConnect: false,
      })
    );

    expect(typeof result.current.undo).toBe('function');
    expect(typeof result.current.redo).toBe('function');
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });

  it('can disconnect cleanly', () => {
    const { result } = renderHook(() =>
      useCollaboration({
        documentId: 'doc-1',
        userId: 'user-1',
        userName: 'Test User',
        autoConnect: false,
      })
    );

    act(() => {
      result.current.disconnect();
    });

    expect(result.current.state.isConnected).toBe(false);
  });
});
