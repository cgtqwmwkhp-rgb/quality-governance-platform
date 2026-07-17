import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import VehicleChecklists, {
  formatKitExpiryLabel,
  isKitAssetType,
  kitExpiryBadgeVariant,
} from '../VehicleChecklists'

const mockListDaily = vi.fn()
const mockListMonthly = vi.fn()
const mockListDefects = vi.fn()
const mockAnalyticsSummary = vi.fn()
const mockAnalyticsTrends = vi.fn()
const mockAnalyticsHeatmap = vi.fn()
const mockApiGet = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  default: {
    get: (...args: unknown[]) => mockApiGet(...args),
  },
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

function renderPage() {
  return render(
    <MemoryRouter>
      <VehicleChecklists />
    </MemoryRouter>,
  )
}

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
    mockApiGet.mockResolvedValue({ data: { assets: [] } })
  })

  it('requests daily checklists with backend-safe page size', async () => {
    renderPage()

    await waitFor(() => {
      expect(mockListDaily).toHaveBeenCalledWith(1, 100)
    })
  })

  it('requests defects with backend-safe page size', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Flagged Defects' }))

    await waitFor(() => {
      expect(mockListDefects).toHaveBeenCalledWith(1, 100, undefined)
    })
  })

  it('shows a stale-data banner when checklist data is served from cache', async () => {
    mockListDaily.mockResolvedValueOnce({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 100,
        pages: 1,
        source: 'cache',
        cache_as_of: '2026-01-03T12:30:00',
      },
    })

    renderPage()

    expect(await screen.findByText('Data may be stale')).toBeInTheDocument()
    expect(screen.getByText('Cache as of 2026-01-03T12:30:00')).toBeInTheDocument()
  })

  it('shows a retry button for checklist load failures', async () => {
    mockListDaily
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce({
        data: { items: [], total: 0, page: 1, page_size: 100, pages: 1, source: 'live' },
      })

    renderPage()

    const retry = await screen.findByRole('button', { name: 'Retry' })
    expect(retry).toBeInTheDocument()

    fireEvent.click(retry)

    await waitFor(() => {
      expect(mockListDaily).toHaveBeenCalledTimes(2)
    })
  })
})

describe('VehicleChecklists van kit compliance panel (AM-VAN)', () => {
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

  it('renders kit assets with expiry status and safety-asset links', async () => {
    mockApiGet.mockResolvedValue({
      data: {
        vehicle_reg: 'AB12CDE',
        assets: [
          {
            id: 42,
            asset_number: 'FE-001',
            name: 'Cabin extinguisher',
            asset_type_id: 1,
            asset_type_name: 'Fire Extinguisher',
            category: 'safety',
            status: 'active',
            expiry_date: '2026-08-01T00:00:00Z',
            expiry_status: 'due_30',
            is_kit_asset: true,
          },
          {
            id: 43,
            asset_number: 'FA-001',
            name: 'First aid pouch',
            asset_type_id: 2,
            asset_type_name: 'First Aid Kit',
            category: 'safety',
            status: 'active',
            expiry_date: '2025-01-01T00:00:00Z',
            expiry_status: 'overdue',
            is_kit_asset: true,
          },
        ],
        fire_extinguisher_expiry: '2026-08-01T00:00:00Z',
        fire_extinguisher_expiry_source: 'asset',
        fire_extinguisher_expiry_status: 'due_30',
        tooling_calibration_expiry: null,
        tooling_calibration_expiry_source: 'none',
        tooling_calibration_expiry_status: 'unknown',
      },
    })

    renderPage()

    const vanInput = await screen.findByPlaceholderText('Filter by van')
    fireEvent.change(vanInput, { target: { value: 'AB12CDE' } })

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/vehicles/AB12CDE/safety-assets')
    })

    expect(await screen.findByTestId('van-kit-compliance-panel')).toBeInTheDocument()
    expect(screen.getByTestId('van-kit-asset-42')).toBeInTheDocument()
    expect(screen.getByTestId('van-kit-asset-43')).toBeInTheDocument()
    expect(screen.getAllByText('Due ≤30d').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Overdue').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByTestId('van-kit-asset-link-42')).toHaveAttribute('href', '/safety-assets/42')
    expect(screen.getByTestId('van-kit-fire-expiry')).toHaveTextContent('Asset register (preferred)')
  })

  it('surfaces kit load failures honestly', async () => {
    mockApiGet.mockRejectedValue(new Error('boom'))

    renderPage()

    const vanInput = await screen.findByPlaceholderText('Filter by van')
    fireEvent.change(vanInput, { target: { value: 'ZZ99ZZZ' } })

    expect(await screen.findByTestId('van-kit-compliance-error')).toHaveTextContent(
      'Unable to load kit assets',
    )
  })
})

describe('AM-VAN kit helpers', () => {
  it('recognises extinguisher / first-aid / tool types', () => {
    expect(isKitAssetType('Fire Extinguisher', 'safety')).toBe(true)
    expect(isKitAssetType('First Aid Kit', null)).toBe(true)
    expect(isKitAssetType('Engineer Tool', 'safety')).toBe(true)
    expect(isKitAssetType('Forklift', 'lifting')).toBe(false)
  })

  it('maps expiry status labels and badge variants', () => {
    expect(formatKitExpiryLabel('overdue')).toBe('Overdue')
    expect(formatKitExpiryLabel('due_30')).toBe('Due ≤30d')
    expect(kitExpiryBadgeVariant('overdue')).toBe('critical')
    expect(kitExpiryBadgeVariant('in_date')).toBe('resolved')
  })
})
