import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import UpstreamDegradedBanner from '../UpstreamDegradedBanner'

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}))

describe('UpstreamDegradedBanner', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders nothing when no circuits are open', () => {
    const { container } = render(
      <UpstreamDegradedBanner openCircuits={[]} halfOpenCircuits={[]} />,
    )
    expect(container.innerHTML).toBe('')
  })

  it('shows controlled open-circuit message', () => {
    render(<UpstreamDegradedBanner openCircuits={['mistral_analysis']} />)
    expect(screen.getByTestId('upstream-degraded-banner')).toBeInTheDocument()
    expect(screen.getByText(/Upstream services degraded/i)).toBeInTheDocument()
    expect(screen.getByText(/mistral_analysis/)).toBeInTheDocument()
  })

  it('polls readyz and surfaces open circuits', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        upstream: {
          ai: {
            circuits: {
              mistral_analysis: { name: 'mistral_analysis', state: 'open' },
              gemini_ai: { name: 'gemini_ai', state: 'closed' },
            },
          },
        },
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<UpstreamDegradedBanner pollReadyz pollIntervalMs={60_000} />)

    await waitFor(() => {
      expect(screen.getByTestId('upstream-degraded-banner')).toBeInTheDocument()
    })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:3000/readyz',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(screen.getByText(/mistral_analysis/)).toBeInTheDocument()
  })

  it('does not claim degradation when readyz fetch fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
    const { container } = render(
      <UpstreamDegradedBanner pollReadyz pollIntervalMs={60_000} />,
    )
    await waitFor(() => {
      expect(container.innerHTML).toBe('')
    })
  })
})
