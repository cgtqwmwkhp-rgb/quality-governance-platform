import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import VehicleChecklists from '../VehicleChecklists'

const mockListDaily = vi.fn()
const mockListMonthly = vi.fn()
const mockListDefects = vi.fn()
const mockAnalyticsSummary = vi.fn()
const mockAnalyticsTrends = vi.fn()
const mockAnalyticsHeatmap = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  vehicleChecklistsApi: {
    listDaily: (...args: unknown[]) => mockListDaily(...args),
    listMonthly: (...args: unknown[]) => mockListMonthly(...args),
    listDefects: (...args: unknown[]) => mockListDefects(...args),
    analyticsSummary: (...args: unknown[]) => mockAnalyticsSummary(...args),
    analyticsTrends: (...args: unknown[]) => mockAnalyticsTrends(...args),
    analyticsHeatmap: (...args: unknown[]) => mockAnalyticsHeatmap(...args),
  },
  getApiErrorMessage: () => 'Request failed',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('VehicleChecklists pagination contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockListDaily.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 1 },
    })
    mockListMonthly.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 1 },
    })
    mockListDefects.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 1 },
    })
    mockAnalyticsSummary.mockResolvedValue({
      data: {
        total_daily_checks: 0,
        total_monthly_checks: 0,
        open_defects: 0,
        p1_defects: 0,
        p2_defects: 0,
        p3_defects: 0,
        overdue_actions: 0,
        last_sync: null,
      },
    })
    mockAnalyticsTrends.mockResolvedValue({ data: [] })
    mockAnalyticsHeatmap.mockResolvedValue({ data: [] })
  })

  it('requests daily checklists with backend-safe page size', async () => {
    render(<VehicleChecklists />)

    await waitFor(() => {
      expect(mockListDaily).toHaveBeenCalledWith(1, 100)
    })
  })

  it('requests defects with backend-safe page size', async () => {
    render(<VehicleChecklists />)

    fireEvent.click(await screen.findByRole('button', { name: 'Flagged Defects' }))

    await waitFor(() => {
      expect(mockListDefects).toHaveBeenCalledWith(1, 100, undefined)
    })
  })
})
