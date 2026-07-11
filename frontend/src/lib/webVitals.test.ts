import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const onCLS = vi.fn()
const onFCP = vi.fn()
const onLCP = vi.fn()
const onTTFB = vi.fn()
const onINP = vi.fn()

vi.mock('web-vitals', () => ({
  onCLS,
  onFCP,
  onLCP,
  onTTFB,
  onINP,
}))

describe('reportWebVitals', () => {
  beforeEach(() => {
    vi.resetModules()
    onCLS.mockReset()
    onFCP.mockReset()
    onLCP.mockReset()
    onTTFB.mockReset()
    onINP.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('registers web-vitals reporters and beacons metrics', async () => {
    const sendBeacon = vi.fn().mockReturnValue(true)
    vi.stubGlobal('navigator', { ...navigator, sendBeacon })

    const { reportWebVitals } = await import('./webVitals')
    reportWebVitals()
    await vi.waitFor(() => expect(onCLS).toHaveBeenCalled())

    expect(onFCP).toHaveBeenCalled()
    expect(onLCP).toHaveBeenCalled()
    expect(onTTFB).toHaveBeenCalled()
    expect(onINP).toHaveBeenCalled()

    const sendMetric = onCLS.mock.calls[0][0] as (metric: {
      name: string
      value: number
      delta: number
      id: string
      rating: string
      navigationType?: string
    }) => void

    sendMetric({
      name: 'CLS',
      value: 0.05,
      delta: 0.01,
      id: 'v1',
      rating: 'good',
      navigationType: 'navigate',
    })

    expect(sendBeacon).toHaveBeenCalled()
    const [, blob] = sendBeacon.mock.calls[0]
    expect(blob).toBeInstanceOf(Blob)
  })

  it('falls back to fetch when sendBeacon is unavailable', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('navigator', { sendBeacon: undefined })

    // Force SEND_BEACON_SUPPORTED false by re-importing after stub
    const { reportWebVitals } = await import('./webVitals')
    reportWebVitals()
    await vi.waitFor(() => expect(onLCP).toHaveBeenCalled())

    const sendMetric = onLCP.mock.calls[0][0] as (metric: {
      name: string
      value: number
      delta: number
      id: string
      rating: string
    }) => void

    sendMetric({ name: 'LCP', value: 1200, delta: 1200, id: 'v2', rating: 'good' })
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/telemetry/web-vitals'),
      expect.objectContaining({ method: 'POST', keepalive: true }),
    )
  })
})
