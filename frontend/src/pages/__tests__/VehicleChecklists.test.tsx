import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import VehicleChecklists, {
  formatChecklistCellValue,
  formatChecklistColumnLabel,
  formatChecklistLoadError,
  formatKitExpiryLabel,
  getFailedCheckLabels,
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
const mockGetApiErrorMessage = vi.fn(() => 'Request failed')

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
  getApiErrorMessage: (...args: unknown[]) => mockGetApiErrorMessage(...args),
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

describe('VehicleChecklists PAMS unavailable honesty (VAN-CL-503)', () => {
  beforeEach(() => {
    vi.clearAllMocks()

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

  it('shows honest PAMS unavailable state instead of filter-empty dash on daily 503', async () => {
    mockGetApiErrorMessage.mockReturnValue(
      'Server error: PAMS unavailable — van checklist data cannot be loaded right now. Please try again shortly.',
    )
    mockListDaily.mockRejectedValue({
      isAxiosError: true,
      response: { status: 503 },
    })

    renderPage()

    expect(await screen.findByTestId('vehicle-checklists-pams-unavailable')).toBeInTheDocument()
    expect(screen.getByTestId('vehicle-checklists-pams-empty')).toBeInTheDocument()
    expect(screen.getAllByText('PAMS unavailable').length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByText('No checklist data matches these filters')).not.toBeInTheDocument()
  })

  it('retries daily load from the PAMS unavailable banner', async () => {
    mockGetApiErrorMessage.mockReturnValue('PAMS unavailable — van checklist data cannot be loaded right now.')
    mockListDaily
      .mockRejectedValueOnce({ response: { status: 503 } })
      .mockResolvedValueOnce({
        data: {
          items: [{ vanReg: 'AB12CDE', brakes: 'pass' }],
          total: 1,
          page: 1,
          page_size: 100,
          pages: 1,
        },
      })

    renderPage()

    expect(await screen.findByTestId('vehicle-checklists-pams-retry')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('vehicle-checklists-pams-retry'))

    await waitFor(() => {
      expect(mockListDaily).toHaveBeenCalledTimes(2)
    })
    expect(await screen.findByText('AB12CDE')).toBeInTheDocument()
    expect(screen.queryByTestId('vehicle-checklists-pams-unavailable')).not.toBeInTheDocument()
  })

  it('normalises checklist load errors to PAMS unavailable copy', () => {
    expect(formatChecklistLoadError('Server error: PAMS database is temporarily unavailable.')).toBe(
      'PAMS unavailable — van checklist data cannot be loaded right now.',
    )
    expect(
      formatChecklistLoadError(
        'PAMS unavailable — van checklist data cannot be loaded right now. Please try again shortly.',
      ),
    ).toContain('PAMS unavailable')
  })
})

describe('VehicleChecklists register presentation (PX-230 / PX-231 / PX-232 / PX-288)', () => {
  beforeEach(() => {
    vi.clearAllMocks()

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

  it('humanises PAMS column keys instead of exposing raw field names (PX-231)', () => {
    expect(formatChecklistColumnLabel('userName')).toBe('Technician')
    expect(formatChecklistColumnLabel('vanID')).toBe('Vehicle')
    expect(formatChecklistColumnLabel('startTimeDate')).toBe('Started')
    expect(formatChecklistColumnLabel('endTimeDate')).toBe('Ended')
    expect(formatChecklistColumnLabel('checkFluids')).toBe('Fluids')
    expect(formatChecklistColumnLabel('checkWheels')).toBe('Wheels')
    expect(formatChecklistColumnLabel('bodyWorkDamage')).toBe('Bodywork damage')
    expect(formatChecklistColumnLabel('inc id')).toBe('Record ID')
  })

  it('formats timestamps as UK dd/mm/yyyy and booleans as Pass/Fail (PX-231 / PX-232)', () => {
    expect(formatChecklistCellValue('startTimeDate', '2026/07/24 16:45:53')).toBe('24/07/2026')
    expect(formatChecklistCellValue('endTimeDate', '2026-07-24T16:45:53')).toBe('24/07/2026')
    expect(formatChecklistCellValue('checkFluids', true)).toBe('Pass')
    expect(formatChecklistCellValue('checkWheels', false)).toBe('Fail')
    expect(formatChecklistCellValue('uploaded', true)).toBe('Yes')
    expect(formatChecklistCellValue('uploaded', 'false')).toBe('No')
  })

  it('surfaces free-text defect notes and failed boolean checks', () => {
    expect(
      getFailedCheckLabels({
        vanID: 'DL73NKG',
        userName: 'Alex',
        checkFluids: true,
        checkWheels: false,
        defects: 'SERVICE LIGHT ON',
      }),
    ).toEqual(['Wheels', 'SERVICE LIGHT ON'])
  })

  it('keeps Flag as the first reachable control on curated records rows (PX-230)', async () => {
    mockListDaily.mockResolvedValue({
      data: {
        items: [
          {
            'inc id': 24958,
            id: 24958,
            userName: 'Alex Driver',
            vanID: 'DL73NKG',
            startTimeDate: '2026/07/24 16:45:53',
            endTimeDate: '2026/07/24 17:02:11',
            mileage: 61234,
            bodyWorkDamage: true,
            defects: 'SERVICE LIGHT ON',
            uploaded: true,
            checkFluids: true,
            checkWheels: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    renderPage()

    expect(await screen.findByTestId('vehicle-checklist-records-table')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Flag' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Vehicle' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Technician' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Started' })).toBeInTheDocument()

    // Raw PAMS keys must not appear as headings.
    expect(screen.queryByRole('columnheader', { name: 'userName' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'vanID' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'startTimeDate' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'inc id' })).not.toBeInTheDocument()

    expect(screen.getByText('DL73NKG')).toBeInTheDocument()
    expect(screen.getByText('Alex Driver')).toBeInTheDocument()
    expect(screen.getAllByText('24/07/2026').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/SERVICE LIGHT ON/)).toBeInTheDocument()

    const flagButton = screen.getByTestId('vehicle-checklist-flag-button')
    expect(flagButton).toBeInTheDocument()
    // Flag is the first interactive control in the row — not buried past 12 columns.
    const row = screen.getByTestId('vehicle-checklist-record-row')
    expect(row.querySelector('[data-testid="vehicle-checklist-flag-button"]')).toBe(flagButton)
    expect(row.firstElementChild?.textContent).toMatch(/Flag/i)
  })

  it('stacks row labels for narrow viewports via responsive classes (PX-288 vehicle)', async () => {
    mockListDaily.mockResolvedValue({
      data: {
        items: [
          {
            userName: 'Sam',
            vanID: 'AB12CDE',
            startTimeDate: '2026-07-22',
            checkFluids: 'pass',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    renderPage()

    const table = await screen.findByTestId('vehicle-checklist-records-table')
    expect(table.querySelector('table')?.className).toMatch(/xl:table/)
    expect(table.querySelector('thead')?.className).toMatch(/xl:table-header-group/)
    // Stacked labels stay in the DOM for tablet/phone; xl hides them.
    const stackedLabels = table.querySelectorAll('td span.xl\\:hidden')
    expect(stackedLabels.length).toBeGreaterThanOrEqual(4)
  })
})
