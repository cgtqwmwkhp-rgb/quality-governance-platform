import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FeatureFlagProvider } from '../FeatureFlagContext'
import { useFeatureFlag, setFeatureFlagOverride, clearFeatureFlagOverride } from '../../hooks/useFeatureFlag'

vi.mock('../../utils/auth', () => ({
  getValidPlatformToken: vi.fn(() => null),
}))

import { getValidPlatformToken } from '../../utils/auth'

const CACHE_KEY = 'ff_cache_v1'

function Probe({ flag = 'compliance_schedule' }: { flag?: string }) {
  const enabled = useFeatureFlag(flag)
  return <span data-testid="flag">{enabled ? 'on' : 'off'}</span>
}

function renderWithProvider(flag?: string) {
  return render(
    <FeatureFlagProvider>
      <Probe flag={flag} />
    </FeatureFlagProvider>,
  )
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

describe('FeatureFlagProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    delete window.__FEATURE_FLAGS__
    vi.mocked(getValidPlatformToken).mockReturnValue(null)
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    localStorage.clear()
    delete window.__FEATURE_FLAGS__
  })

  it('reveals a feature once the server confirms it', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ flags: { compliance_schedule: true }, scope: 'user' }),
    )

    renderWithProvider()
    // Subtract-only: hidden until confirmed, never revealed by missing information.
    expect(screen.getByTestId('flag')).toHaveTextContent('off')

    await waitFor(() => expect(screen.getByTestId('flag')).toHaveTextContent('on'))
  })

  it('keeps a feature hidden when the server says false', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ flags: { compliance_schedule: false }, scope: 'user' }),
    )

    renderWithProvider()
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    expect(screen.getByTestId('flag')).toHaveTextContent('off')
  })

  it('seeds synchronously from a fresh cache, so a returning user sees no flash', () => {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        flags: { compliance_schedule: true },
        fetchedAt: Date.now(),
        scope: 'user',
      }),
    )
    vi.mocked(fetch).mockImplementation(() => new Promise(() => {}))

    renderWithProvider()
    // Asserted before any await: the very first render already has the value.
    expect(screen.getByTestId('flag')).toHaveTextContent('on')
  })

  it('ignores a cache older than the staleness bound', () => {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        flags: { compliance_schedule: true },
        fetchedAt: Date.now() - 25 * 60 * 60 * 1000,
        scope: 'user',
      }),
    )
    vi.mocked(fetch).mockImplementation(() => new Promise(() => {}))

    renderWithProvider()
    expect(screen.getByTestId('flag')).toHaveTextContent('off')
  })

  it('keeps the cached value when the network fails', async () => {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        flags: { compliance_schedule: true },
        fetchedAt: Date.now(),
        scope: 'user',
      }),
    )
    vi.mocked(fetch).mockRejectedValue(new Error('offline'))

    renderWithProvider()
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    // Failing closed here would black out the UI during a blip and protect nothing.
    expect(screen.getByTestId('flag')).toHaveTextContent('on')
  })

  it('keeps the cached value when the response body is malformed', async () => {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        flags: { compliance_schedule: true },
        fetchedAt: Date.now(),
        scope: 'user',
      }),
    )
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ nonsense: true }))

    renderWithProvider()
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    expect(screen.getByTestId('flag')).toHaveTextContent('on')
  })

  it('falls back to defaults and stops asking when the endpoint is absent', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}, 404))

    renderWithProvider('admin_user_management')
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1))
    // admin_user_management defaults true, so a 404 must not black out admin tooling.
    expect(screen.getByTestId('flag')).toHaveTextContent('on')
  })

  it('does not let a 5xx overwrite what is already known', async () => {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        flags: { compliance_schedule: true },
        fetchedAt: Date.now(),
        scope: 'user',
      }),
    )
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ error: 'boom' }, 503))

    renderWithProvider()
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    expect(screen.getByTestId('flag')).toHaveTextContent('on')
  })

  it('lets a localStorage override beat the server', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ flags: { compliance_schedule: false }, scope: 'user' }),
    )
    setFeatureFlagOverride('compliance_schedule', true)

    renderWithProvider()
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    expect(screen.getByTestId('flag')).toHaveTextContent('on')

    clearFeatureFlagOverride('compliance_schedule')
  })

  it('sends the bearer token so the server can fold in permissions', async () => {
    vi.mocked(getValidPlatformToken).mockReturnValue('tok-123')
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ flags: {}, scope: 'user' }))

    renderWithProvider()

    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    const [, init] = vi.mocked(fetch).mock.calls[0]
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer tok-123')
  })

  it('omits the header entirely when there is no token', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ flags: {}, scope: 'anonymous' }))

    renderWithProvider()

    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    const [, init] = vi.mocked(fetch).mock.calls[0]
    expect((init?.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('requests the meta features endpoint', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ flags: {}, scope: 'anonymous' }))

    renderWithProvider()

    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    const [url] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('/api/v1/meta/features')
  })

  it('mirrors server flags onto window so the documented precedence stays true', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ flags: { compliance_schedule: true }, scope: 'user' }),
    )

    renderWithProvider()
    await waitFor(() => expect(window.__FEATURE_FLAGS__?.compliance_schedule).toBe(true))
  })
})
