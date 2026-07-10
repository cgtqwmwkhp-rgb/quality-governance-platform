import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RiskRegister from '../RiskRegister'

vi.mock('../../api/client', () => ({
  riskRegisterApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    getSummary: vi.fn().mockResolvedValue({ data: {} }),
    getHeatmap: vi.fn().mockResolvedValue({ data: { cells: [] } }),
    resolveSuggestionTriage: vi.fn(),
  },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

describe('RiskRegister bow-tie gate', () => {
  beforeEach(() => {
    localStorage.clear()
    delete window.__FEATURE_FLAGS__
  })

  it('hides unfinished bow-tie UI and fabricated labels by default', async () => {
    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Enterprise Risk Register' })

    expect(screen.queryByRole('button', { name: /bow-tie analysis/i })).not.toBeInTheDocument()
    expect(
      screen.queryByText(/equipment failure|financial loss|human error|preventive maintenance/i),
    ).not.toBeInTheDocument()
  })
})
