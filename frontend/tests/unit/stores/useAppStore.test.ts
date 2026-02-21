import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '../../../src/stores/useAppStore';

describe('useAppStore', () => {
  beforeEach(() => {
    const store = useAppStore.getState();
    store.setLoading(false);
    store.setConnectionStatus('connected');
  });

  it('initializes with default state', () => {
    const state = useAppStore.getState();
    expect(state.isLoading).toBe(false);
    expect(state.connectionStatus).toBe('connected');
    expect(typeof state.isOnline).toBe('boolean');
  });

  it('setLoading updates loading state', () => {
    useAppStore.getState().setLoading(true);
    expect(useAppStore.getState().isLoading).toBe(true);

    useAppStore.getState().setLoading(false);
    expect(useAppStore.getState().isLoading).toBe(false);
  });

  it('setConnectionStatus updates connection status', () => {
    useAppStore.getState().setConnectionStatus('disconnected');
    expect(useAppStore.getState().connectionStatus).toBe('disconnected');

    useAppStore.getState().setConnectionStatus('reconnecting');
    expect(useAppStore.getState().connectionStatus).toBe('reconnecting');
  });

  it('setOnline updates online status', () => {
    useAppStore.getState().setOnline(false);
    expect(useAppStore.getState().isOnline).toBe(false);

    useAppStore.getState().setOnline(true);
    expect(useAppStore.getState().isOnline).toBe(true);
  });
});
