import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const listAssetTypes = vi.fn().mockResolvedValue({ data: { items: [] } })
const getEngineer = vi.fn()
const getCompetencies = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('../../../api/client', () => ({
  workforceApi: {
    listAssetTypes,
    getEngineer,
    getCompetencies,
  },
  getApiErrorMessage: () => 'load failed',
}))

vi.mock('../../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

describe('EngineerProfile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listAssetTypes.mockResolvedValue({ data: { items: [] } })
  })

  it('shows not found state for invalid engineer ids without loading forever', async () => {
    const EngineerProfile = (await import('../EngineerProfile')).default

    render(
      <MemoryRouter initialEntries={['/workforce/engineers/abc']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('workforce.engineers.not_found')).toBeInTheDocument()
    expect(getEngineer).not.toHaveBeenCalled()
    expect(getCompetencies).not.toHaveBeenCalled()
  })
})
