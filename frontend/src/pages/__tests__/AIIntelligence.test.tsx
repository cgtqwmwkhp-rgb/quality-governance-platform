import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const isAIIntelligenceRouteEnabledMock = vi.fn(() => false)

vi.mock('../../config/aiIntelligenceRoute', () => ({
  isAIIntelligenceRouteEnabled: () => isAIIntelligenceRouteEnabledMock(),
}))

describe('AIIntelligence alias', () => {
  beforeEach(() => {
    isAIIntelligenceRouteEnabledMock.mockReset()
    isAIIntelligenceRouteEnabledMock.mockReturnValue(false)
  })

  async function renderAlias() {
    const AIIntelligence = (await import('../AIIntelligence')).default

    render(
      <MemoryRouter initialEntries={['/ai-intelligence']}>
        <Routes>
          <Route path="/ai-intelligence" element={<AIIntelligence />} />
          <Route
            path="/analytics/safety-insights"
            element={<div>Safety Insights Analyst</div>}
          />
        </Routes>
      </MemoryRouter>,
    )
  }

  // Defence in depth: App.tsx omits the route while the flag is off, so this
  // covers the case where some future caller mounts the alias anyway.
  it('renders a 404 instead of the Analyst redirect while the flag is off', async () => {
    await renderAlias()

    expect(screen.getByText('404')).toBeInTheDocument()
    expect(screen.queryByText('Safety Insights Analyst')).not.toBeInTheDocument()
  })

  it('redirects to the Safety Insights Analyst when the flag is on', async () => {
    isAIIntelligenceRouteEnabledMock.mockReturnValue(true)

    await renderAlias()

    expect(screen.getByText('Safety Insights Analyst')).toBeInTheDocument()
    expect(screen.queryByText('404')).not.toBeInTheDocument()
  })
})
