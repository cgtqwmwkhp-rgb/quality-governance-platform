import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '../../../src/stores/useAppStore';

describe('useAppStore', () => {
  beforeEach(() => {
    useAppStore.setState({
      isLoading: false,
      isOnline: true,
      connectionStatus: 'connected',
    });
  });

  it('should initialize with default state', () => {
    const state = useAppStore.getState();
    expect(state.isLoading).toBe(false);
    expect(state.connectionStatus).toBe('connected');
  });

  it('should track loading state', () => {
    useAppStore.getState().setLoading(true);
    expect(useAppStore.getState().isLoading).toBe(true);

    useAppStore.getState().setLoading(false);
    expect(useAppStore.getState().isLoading).toBe(false);
  });

  it('should track online status', () => {
    useAppStore.getState().setOnline(false);
    expect(useAppStore.getState().isOnline).toBe(false);

    useAppStore.getState().setOnline(true);
    expect(useAppStore.getState().isOnline).toBe(true);
  });

  it('should track connection status', () => {
    useAppStore.getState().setConnectionStatus('disconnected');
    expect(useAppStore.getState().connectionStatus).toBe('disconnected');

    useAppStore.getState().setConnectionStatus('reconnecting');
    expect(useAppStore.getState().connectionStatus).toBe('reconnecting');

    useAppStore.getState().setConnectionStatus('connected');
    expect(useAppStore.getState().connectionStatus).toBe('connected');
  });
});
