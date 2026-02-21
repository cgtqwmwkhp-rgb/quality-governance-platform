import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGeolocation } from '../../../src/hooks/useGeolocation';

describe('useGeolocation', () => {
  const mockPosition: GeolocationPosition = {
    coords: {
      latitude: 51.5074,
      longitude: -0.1278,
      accuracy: 10,
      altitude: null,
      altitudeAccuracy: null,
      heading: null,
      speed: null,
    },
    timestamp: Date.now(),
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with null coordinates and no loading state', () => {
    const { result } = renderHook(() => useGeolocation());
    expect(result.current.latitude).toBeNull();
    expect(result.current.longitude).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('returns location on successful geolocation call', async () => {
    const mockGetCurrentPosition = vi.fn(
      (success: PositionCallback) => success(mockPosition)
    );
    Object.defineProperty(navigator, 'geolocation', {
      value: { getCurrentPosition: mockGetCurrentPosition },
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useGeolocation());

    await act(async () => {
      await result.current.getLocation();
    });

    expect(result.current.latitude).toBe(51.5074);
    expect(result.current.longitude).toBe(-0.1278);
    expect(result.current.accuracy).toBe(10);
    expect(result.current.error).toBeNull();
  });

  it('sets error when geolocation is not supported', async () => {
    Object.defineProperty(navigator, 'geolocation', {
      value: undefined,
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useGeolocation());

    await act(async () => {
      await result.current.getLocation();
    });

    expect(result.current.error).toBe('Geolocation is not supported by your browser');
  });

  it('formats location string correctly', async () => {
    const mockGetCurrentPosition = vi.fn(
      (success: PositionCallback) => success(mockPosition)
    );
    Object.defineProperty(navigator, 'geolocation', {
      value: { getCurrentPosition: mockGetCurrentPosition },
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useGeolocation());

    let locationString: string | null = null;
    await act(async () => {
      locationString = await result.current.getLocationString();
    });

    expect(locationString).toBe('GPS: 51.507400, -0.127800 (±10m)');
  });

  it('clears error via clearError', async () => {
    Object.defineProperty(navigator, 'geolocation', {
      value: undefined,
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useGeolocation());

    await act(async () => {
      await result.current.getLocation();
    });
    expect(result.current.error).not.toBeNull();

    act(() => {
      result.current.clearError();
    });
    expect(result.current.error).toBeNull();
  });
});
