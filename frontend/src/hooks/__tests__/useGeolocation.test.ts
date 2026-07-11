import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useGeolocation } from '../useGeolocation'

describe('useGeolocation', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reports unsupported geolocation', async () => {
    vi.stubGlobal('navigator', { geolocation: undefined })
    const { result } = renderHook(() => useGeolocation())

    let position: GeolocationPosition | null = null
    await act(async () => {
      position = await result.current.getLocation()
    })
    expect(position).toBeNull()
    expect(result.current.error).toMatch(/not supported/i)
  })

  it('resolves coordinates and location string on success', async () => {
    const mockPosition = {
      coords: { latitude: 51.5, longitude: -0.12, accuracy: 12 },
    } as GeolocationPosition
    const getCurrentPosition = vi.fn((success: PositionCallback) => {
      success(mockPosition)
    })
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition } })

    const { result } = renderHook(() => useGeolocation({ timeout: 1000 }))
    await act(async () => {
      await result.current.getLocation()
    })
    expect(result.current.latitude).toBe(51.5)
    expect(result.current.longitude).toBe(-0.12)
    expect(result.current.isLoading).toBe(false)

    let label: string | null = null
    await act(async () => {
      label = await result.current.getLocationString()
    })
    expect(label).toContain('GPS:')
    expect(label).toContain('51.500000')
  })

  it('maps permission denied errors and clearError resets them', async () => {
    class FakeGeoError extends Error {
      code = 1
      PERMISSION_DENIED = 1
      POSITION_UNAVAILABLE = 2
      TIMEOUT = 3
    }
    vi.stubGlobal('GeolocationPositionError', FakeGeoError)
    const getCurrentPosition = vi.fn((_s: PositionCallback, error: PositionErrorCallback) => {
      error(new FakeGeoError('denied') as unknown as GeolocationPositionError)
    })
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition } })

    const { result } = renderHook(() => useGeolocation())
    await act(async () => {
      await result.current.getLocation()
    })
    expect(result.current.error).toMatch(/permission denied/i)

    act(() => {
      result.current.clearError()
    })
    expect(result.current.error).toBeNull()
  })

  it('maps unavailable and timeout geolocation errors', async () => {
    class FakeGeoError extends Error {
      code: number
      PERMISSION_DENIED = 1
      POSITION_UNAVAILABLE = 2
      TIMEOUT = 3
      constructor(code: number) {
        super('geo')
        this.code = code
      }
    }
    vi.stubGlobal('GeolocationPositionError', FakeGeoError)

    const unavailable = vi.fn((_s: PositionCallback, error: PositionErrorCallback) => {
      error(new FakeGeoError(2) as unknown as GeolocationPositionError)
    })
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: unavailable } })
    const { result, rerender } = renderHook(() => useGeolocation())
    await act(async () => {
      await result.current.getLocation()
    })
    expect(result.current.error).toMatch(/unavailable/i)

    const timedOut = vi.fn((_s: PositionCallback, error: PositionErrorCallback) => {
      error(new FakeGeoError(3) as unknown as GeolocationPositionError)
    })
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: timedOut } })
    rerender()
    await act(async () => {
      await result.current.getLocation()
    })
    expect(result.current.error).toMatch(/timed out/i)
  })
})
