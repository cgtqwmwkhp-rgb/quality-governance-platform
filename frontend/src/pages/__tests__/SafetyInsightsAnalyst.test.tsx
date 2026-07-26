import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SafetyInsightsAnalyst from '../SafetyInsightsAnalyst'

const startRun = vi.fn()
const listRuns = vi.fn()
const getRun = vi.fn()

vi.mock('../../api/client', () => ({
  safetyInsightsApi: {
    startRun: (...args: unknown[]) => startRun(...args),
    listRuns: (...args: unknown[]) => listRuns(...args),
    getRun: (...args: unknown[]) => getRun(...args),
  },
}))

vi.mock('react-i18next', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-i18next')>()
  return {
    ...actual,
    useTranslation: () => ({
      t: (_key: string, opts?: { defaultValue?: string }) => opts?.defaultValue || _key,
      i18n: { language: 'en' },
    }),
  }
})

describe('SafetyInsightsAnalyst', () => {
  beforeEach(() => {
    startRun.mockReset()
    listRuns.mockReset()
    getRun.mockReset()
    listRuns.mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it('PX-285/PX-165: surfaces external-processor disclosure before run', () => {
    render(
      <MemoryRouter>
        <SafetyInsightsAnalyst />
      </MemoryRouter>,
    )

    const notice = screen.getByTestId('safety-insights-external-processing-notice')
    expect(notice).toHaveTextContent(/Google Gemini/i)
    expect(notice).toHaveTextContent(/Anthropic Claude/i)
    expect(notice).toHaveTextContent(/Perplexity/i)
    expect(notice).toHaveTextContent(/DPIA/i)
    expect(screen.getByRole('button', { name: /Run deep analysis/i })).toBeDisabled()
  })

  it('does not start a run until external processing is acknowledged', async () => {
    render(
      <MemoryRouter>
        <SafetyInsightsAnalyst />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /Run deep analysis/i }))
    expect(startRun).not.toHaveBeenCalled()
  })

  it('posts deep-run payload with external_processing_acknowledged after consent', async () => {
    startRun.mockResolvedValue({
      data: {
        id: 7,
        status: 'queued',
        progress_pct: 0,
        modules: ['incident', 'near_miss', 'rta', 'complaint'],
        scope: 'org',
        min_cluster_size: 2,
        include_synthesis: true,
        include_benchmark: false,
        synthesis_available: false,
        research_available: false,
      },
    })

    render(
      <MemoryRouter>
        <SafetyInsightsAnalyst />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByTestId('safety-insights-external-processing-ack'))
    fireEvent.click(screen.getByRole('button', { name: /Run deep analysis/i }))

    await waitFor(() => expect(startRun).toHaveBeenCalled())
    expect(startRun.mock.calls[0][0]).toMatchObject({
      modules: ['incident', 'near_miss', 'rta', 'complaint'],
      scope: 'org',
      min_cluster_size: 2,
      include_synthesis: true,
      include_benchmark: false,
      external_processing_acknowledged: true,
    })
  })
})
