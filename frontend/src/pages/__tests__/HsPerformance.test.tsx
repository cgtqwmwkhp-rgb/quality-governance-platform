import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mockGetSummary = vi.fn()

vi.mock('../../api/client', () => ({
  hsKpisApi: {
    getSummary: (...args: unknown[]) => mockGetSummary(...args),
    dryRunExcelImport: vi.fn(),
    commitExcelImport: vi.fn(),
  },
}))

describe('HsPerformance (PX-270)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders unavailable LTIFR without printing 0.00', async () => {
    mockGetSummary.mockResolvedValue({
      data: {
        rate_unit: 'per_100000_hours',
        by_year: [
          {
            reporting_year: 2026,
            period_start: '2026-01-01',
            period_end: '2026-12-31',
            average_fte: 100,
            hours: 200000,
            injuries: 5,
            near_misses: 10,
            hipo_near_misses: 1,
            rtas: 2,
            complaints: 0,
            ltis: 0,
            riddor: 0,
            ltifr: null,
            ltifr_unavailable_reason: 'no_lti_classification',
            afr: 2.5,
            afr_unavailable_reason: null,
            rate_unit: 'per_100000_hours',
          },
        ],
      },
    })

    const HsPerformance = (await import('../HsPerformance')).default
    render(
      <MemoryRouter>
        <HsPerformance />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('hs-kpi-ltifr')).toBeInTheDocument()
    })
    expect(screen.getByTestId('hs-kpi-ltifr')).toHaveTextContent('—')
    expect(screen.getByTestId('hs-kpi-ltifr')).not.toHaveTextContent('0.00')
    expect(screen.getByTestId('hs-kpi-ltifr-reason')).toHaveTextContent(/lost time/i)
    expect(screen.getByTestId('hs-table-ltifr-2026')).toHaveTextContent('—')
  })
})
