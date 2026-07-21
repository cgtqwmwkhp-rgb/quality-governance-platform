import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import SafetyAssetRegister from '../SafetyAssetRegister'

const mockListAllAssetsForBoard = vi.fn()
const mockListAssetTypes = vi.fn()
const mockListLocations = vi.fn()
const mockListEngineers = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | Record<string, unknown>) => {
      if (typeof fallback === 'string') return fallback
      if (fallback && typeof fallback === 'object' && 'defaultValue' in fallback) {
        return String(fallback.defaultValue)
      }
      if (fallback && typeof fallback === 'object' && 'count' in fallback) {
        return `${fallback.count} assets`
      }
      return key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/safetyAssetsClient', () => ({
  EMPTY_SAFETY_ASSET_KPIS: {
    total: null,
    in_date: null,
    due_30: null,
    due_60: null,
    due_90: null,
    overdue: null,
    quarantined: null,
  },
  safetyAssetsApi: {
    listAllAssetsForBoard: (...args: unknown[]) => mockListAllAssetsForBoard(...args),
    listAssetTypes: (...args: unknown[]) => mockListAssetTypes(...args),
    listLocations: (...args: unknown[]) => mockListLocations(...args),
    cesImportDryRun: vi.fn(),
    cesImportCommit: vi.fn(),
  },
}))

vi.mock('../../api/client', () => ({
  getApiErrorMessage: () => 'Request failed',
  workforceApi: {
    listEngineers: (...args: unknown[]) => mockListEngineers(...args),
  },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

describe('SafetyAssetRegister Wave 2 board', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListAssetTypes.mockResolvedValue({ data: { items: [], total: 0 } })
    mockListLocations.mockResolvedValue({ data: { items: [], total: 0 } })
    mockListEngineers.mockResolvedValue({ data: { items: [] } })
  })

  it('renders em dashes for KPIs when load fails (no silent zeros)', async () => {
    mockListAllAssetsForBoard.mockRejectedValue(new Error('boom'))

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-kpi-unavailable')).toBeInTheDocument()
    })

    expect(screen.getByTestId('safety-assets-kpi-total')).toHaveTextContent('—')
    expect(screen.getByTestId('safety-assets-kpi-overdue')).toHaveTextContent('—')
    expect(screen.getByTestId('safety-assets-kpi-quarantined')).toHaveTextContent('—')
  })

  it('renders asset rows and engineer rollup drill-in', async () => {
    mockListAssetTypes.mockResolvedValue({
      data: {
        items: [{ id: 10, category: 'safety', name: 'Harness', is_active: true }],
        total: 1,
      },
    })
    mockListEngineers.mockResolvedValue({
      data: { items: [{ id: 1, user_id: 3, display_name: 'Alex Owner', is_active: true }] },
    })
    mockListAllAssetsForBoard.mockResolvedValue([
      {
        id: 55,
        external_id: 'ext-55',
        asset_type_id: 10,
        asset_number: 'SA-001',
        name: 'Fall harness A',
        status: 'active',
        serial_number: 'SN-55',
        vehicle_reg: 'AB12CDE',
        owner_user_id: 3,
        expiry_date: '2026-12-01T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-table')).toBeInTheDocument()
    })

    expect(screen.getByTestId('safety-asset-row-55')).toBeInTheDocument()
    expect(screen.getByText('SN-55')).toBeInTheDocument()
    expect(screen.getByText('Fall harness A')).toBeInTheDocument()
    expect(screen.getByTestId('safety-assets-kpi-total')).toHaveTextContent('1')
    expect(screen.queryByTestId('safety-assets-kpi-unavailable')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('safety-assets-view-engineer'))
    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-engineer-table')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('safety-assets-rollup-user:3'))
    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-drilldown-sheet')).toBeInTheDocument()
    })
    expect(screen.getByTestId('safety-assets-sheet-row-55')).toBeInTheDocument()
  })

  it('shows CES upload panel on upload view', async () => {
    mockListAllAssetsForBoard.mockResolvedValue([])

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-view-upload')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('safety-assets-view-upload'))
    expect(screen.getByTestId('ces-import-panel')).toBeInTheDocument()
  })
})
