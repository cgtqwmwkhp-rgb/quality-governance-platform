import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useServiceWorker } from '../../../src/hooks/useServiceWorker';

describe('useServiceWorker', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('detects when service workers are not supported', () => {
    const originalSW = navigator.serviceWorker;
    Object.defineProperty(navigator, 'serviceWorker', {
      value: undefined,
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useServiceWorker());

    expect(result.current.isSupported).toBe(false);
    expect(result.current.isRegistered).toBe(false);

    Object.defineProperty(navigator, 'serviceWorker', {
      value: originalSW,
      writable: true,
      configurable: true,
    });
  });

  it('reports online/offline status', () => {
    const { result } = renderHook(() => useServiceWorker());
    expect(typeof result.current.isOnline).toBe('boolean');
  });

  it('exposes the expected API methods', () => {
    const { result } = renderHook(() => useServiceWorker());
    expect(typeof result.current.registerSW).toBe('function');
    expect(typeof result.current.updateSW).toBe('function');
    expect(typeof result.current.subscribeToPush).toBe('function');
    expect(typeof result.current.unsubscribeFromPush).toBe('function');
    expect(typeof result.current.savePendingReport).toBe('function');
    expect(typeof result.current.syncPendingReports).toBe('function');
  });

  it('initializes with hasUpdate as false', () => {
    const { result } = renderHook(() => useServiceWorker());
    expect(result.current.hasUpdate).toBe(false);
  });

  it('initializes with null registration and pushSubscription', () => {
    const { result } = renderHook(() => useServiceWorker());
    expect(result.current.registration).toBeNull();
    expect(result.current.pushSubscription).toBeNull();
  });
});
